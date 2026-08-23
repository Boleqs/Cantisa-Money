import io
import re
import unicodedata

# Pas ancrée en fin de ligne : les tickets français ajoutent souvent une lettre de code TVA
# après le montant (ex: "2,69 A T"), donc on prend le DERNIER nombre décimal trouvé sur la
# ligne, quel que soit ce qui le suit (lettres de code, symboles mal lus par l'OCR...).
PRICE_RE = re.compile(r'\d{1,4}[.,]\d{2}')
DATE_RE = re.compile(r'\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})\b')

# Lignes à ignorer : récapitulatifs de paiement/TVA, en-têtes, pied de ticket — pas des articles.
NOISE_KEYWORDS = (
    'SOUS-TOTAL', 'SOUS TOTAL', 'TVA', 'ESPECES', 'ESPÈCES', 'CB', 'CARTE',
    'RENDU', 'MERCI', 'TICKET', 'CAISSE', 'SIRET', 'TEL', 'TÉL',
    'HORAIRES', 'OUVERT', 'FERMÉ', 'FERME', 'CODE', 'BARRE', 'RCS', 'INTRACOM',
    'DUPLICATA', 'MODE DE PAIEMENT', 'NB ARTICLES', 'NOMBRE DE LIGNES', 'ARTICLES',
    'RESTAURANT', 'TITRES', 'LIGIBLE', 'MONT', 'TTC', 'TOTAL HT', 'PLUS',
)

# Lignes qui indiquent le montant total du ticket (pas forcément le mot "TOTAL" — les
# tickets Lidl/Carrefour etc. disent souvent "À payer").
TOTAL_KEYWORDS = ('PAYER', 'TOTAL')

# Labels valides pour une zone de gabarit (voir ReceiptTemplates.zones) — partagé avec
# rt_receipt_templates.py pour valider les zones à l'enregistrement.
TEMPLATE_ZONE_LABELS = ('marchand', 'date', 'total', 'articles')

# Instance EasyOCR (coûteuse à charger — modèles chargés en mémoire) : créée une seule fois au
# premier OCR puis réutilisée, jamais à chaque requête.
_easyocr_reader = None


def _looks_like_noise(line_upper):
    if '%' in line_upper:  # ligne de taux de TVA (ex: "A 5,5% 15,77 0,82 14,95")
        return True
    return any(kw in line_upper for kw in NOISE_KEYWORDS)


def _preprocess(image):
    """Étirement du contraste : améliore la lecture des tickets thermiques pâles ou photographiés
    avec un éclairage inégal, sans passer en niveaux de gris (EasyOCR est entraîné sur des images
    couleur et gère déjà en interne le contraste/l'éclairage)."""
    from PIL import ImageOps
    return ImageOps.autocontrast(image.convert('RGB'))


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(['fr'], gpu=False)
    return _easyocr_reader


def _reconstruct_lines(items):
    """items: liste de (bbox, texte) où bbox est une liste de points [x, y] entourant une
    détection individuelle (mot ou courte phrase) — EasyOCR détecte par mot/segment, pas par ligne
    complète. Reconstruit des LIGNES façon tableau en regroupant les détections de hauteur (y)
    proche puis en les triant par x — sans ça, un libellé et son prix (deux détections séparées à
    la même hauteur sur un ticket) finissent sur des lignes distinctes du texte final et cassent
    _parse_item_lines(), qui exige libellé+prix sur une MÊME ligne."""
    boxes = []
    for bbox, text in items:
        if not text:
            continue
        ys = [p[1] for p in bbox]
        xs = [p[0] for p in bbox]
        boxes.append({'text': text, 'y': sum(ys) / len(ys), 'x': min(xs), 'height': max(ys) - min(ys) or 10})
    if not boxes:
        return ''
    boxes.sort(key=lambda b: b['y'])

    lines = [[boxes[0]]]
    for b in boxes[1:]:
        current = lines[-1]
        ref_y = sum(c['y'] for c in current) / len(current)
        avg_h = sum(c['height'] for c in current) / len(current)
        if abs(b['y'] - ref_y) <= avg_h * 0.6:
            current.append(b)
        else:
            lines.append([b])

    return '\n'.join(' '.join(c['text'] for c in sorted(line, key=lambda c: c['x'])) for line in lines)


def _run_ocr(image):
    """Texte OCR d'une image déjà prétraitée (_preprocess), reconstruit en lignes façon tableau
    (voir _reconstruct_lines)."""
    import numpy as np

    reader = _get_easyocr_reader()
    # detail=1, paragraph=False : détections individuelles avec leurs coordonnées — nécessaire
    # pour _reconstruct_lines (le mode paragraph=True regroupe en prose et perd l'alignement
    # libellé/prix en colonnes).
    detections = reader.readtext(np.array(image), detail=1, paragraph=False)
    items = [(bbox, text) for bbox, text, conf in detections]
    return _reconstruct_lines(items)


def normalize_merchant_key(name):
    """Nom de marchand -> clé de correspondance stable (majuscules, sans accents, espaces
    compactés) — même principe que ImportCategoryRules.keyword, pour reconnaître 'Super Frais' et
    'SUPER  FRAIS' comme le même marchand d'un ticket à l'autre."""
    if not name:
        return ''
    stripped = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', stripped).strip().upper()


def load_image(file_bytes, mime_type):
    """Image PIL brute (RGB, non prétraitée) pour l'application d'un gabarit — None si le format
    n'est pas directement exploitable en zones (PDF : non géré par les gabarits pour l'instant,
    la mise en page y varie moins d'un document à l'autre qu'une photo de ticket, l'intérêt est
    plus faible)."""
    if mime_type == 'application/pdf':
        return None
    from PIL import Image
    return Image.open(io.BytesIO(file_bytes)).convert('RGB')


def extract_text(file_bytes, mime_type):
    """Retourne le texte brut lu par OCR (images) ou extrait/OCRisé (PDF)."""
    from PIL import Image

    if mime_type == 'application/pdf':
        import fitz  # PyMuPDF

        doc = fitz.open(stream=file_bytes, filetype='pdf')
        pages_text = []
        for page in doc:
            text = page.get_text().strip()
            if not text:
                # PDF scanné (pas de couche texte) : on rasterise puis on OCRise
                pix = page.get_pixmap(dpi=300)
                image = _preprocess(Image.open(io.BytesIO(pix.tobytes('png'))))
                text = _run_ocr(image)
            pages_text.append(text)
        return '\n'.join(pages_text)

    image = _preprocess(Image.open(io.BytesIO(file_bytes)))
    return _run_ocr(image)


def _parse_item_lines(lines_raw, user_tags=None):
    """Isole les lignes d'articles (libellé + montant) d'une liste de lignes déjà nettoyées —
    factorisé pour être réutilisé tel quel sur le texte OCR d'une zone 'articles' de gabarit
    (apply_template) comme sur une lecture pleine page (parse_receipt). Retourne (items, total_found)."""
    user_tags = user_tags or []
    total_found = None
    items = []
    for line in lines_raw:
        upper = line.upper()
        price_matches = list(PRICE_RE.finditer(line))
        if not price_matches:
            continue
        # Le libellé s'arrête au premier nombre de la ligne (avant les colonnes prix
        # unitaire/quantité) ; le montant retenu est le dernier (la colonne total).
        amount = float(price_matches[-1].group().replace(',', '.'))
        label = line[:price_matches[0].start()].strip(' .:-')

        if any(kw in upper for kw in TOTAL_KEYWORDS) and 'SOUS' not in upper:
            total_found = amount
            continue
        if _looks_like_noise(upper) or not label:
            continue

        suggested_tag_id = None
        label_lower = label.lower()
        for tag in user_tags:
            if tag['name'].lower() in label_lower:
                suggested_tag_id = tag['id']
                break

        items.append({'label': label, 'amount': amount, 'suggested_tag_id': suggested_tag_id})
    return items, total_found


def parse_receipt(raw_text, user_tags=None):
    """Parse le texte OCR d'un ticket de caisse en lignes d'articles.

    user_tags: liste de {'id': str, 'name': str} pour suggérer un tag par mot-clé.
    Retourne {merchant, date, total, lines, warnings}.
    """
    user_tags = user_tags or []
    lines_raw = [l.strip() for l in raw_text.splitlines() if l.strip()]

    merchant = next((l for l in lines_raw if not PRICE_RE.search(l) and len(l) > 2), None)

    date_found = None
    m = DATE_RE.search(raw_text)
    if m:
        day, month, year = m.groups()
        if len(year) == 2:
            year = '20' + year
        try:
            date_found = f"{year}-{int(month):02d}-{int(day):02d}"
        except ValueError:
            date_found = None

    items, total_found = _parse_item_lines(lines_raw, user_tags)

    warnings = []
    if total_found is not None:
        items_sum = round(sum(i['amount'] for i in items), 2)
        if abs(items_sum - total_found) > 0.01:
            warnings.append(
                f"La somme des lignes détectées ({items_sum}) ne correspond pas au total lu sur le ticket ({total_found}) — vérifie les lignes avant de valider."
            )
    if not items:
        warnings.append("Aucune ligne d'article détectée automatiquement — l'OCR n'a peut-être pas bien lu le ticket.")

    return {
        'merchant': merchant,
        'date': date_found,
        'total': total_found,
        'lines': items,
        'warnings': warnings,
    }


def _crop_zone(image, zone):
    """image: PIL Image brute. zone: {'top','left','width','height'} en pourcentage (0-100) de
    l'image. Élargit la zone d'une marge de tolérance (15% de sa taille) : les coordonnées viennent
    d'une AUTRE photo du même ticket, jamais cadrée à l'identique — mieux vaut une zone un peu large
    que risquer de couper le texte visé."""
    w, h = image.size
    left = zone['left'] / 100 * w
    top = zone['top'] / 100 * h
    right = left + zone['width'] / 100 * w
    bottom = top + zone['height'] / 100 * h

    margin_x = zone['width'] / 100 * w * 0.15
    margin_y = zone['height'] / 100 * h * 0.15
    left = max(0, left - margin_x)
    top = max(0, top - margin_y)
    right = min(w, right + margin_x)
    bottom = min(h, bottom + margin_y)
    return image.crop((int(left), int(top), int(right), int(bottom)))


def _ocr_zone(cropped):
    processed = _preprocess(cropped)
    # Zone étroite (souvent une simple ligne de texte après recadrage) : on agrandit avant OCR —
    # un texte devenu minuscule une fois la zone isolée du reste du ticket se lit mal.
    if processed.width < 300:
        ratio = 300 / processed.width
        processed = processed.resize((max(1, int(processed.width * ratio)), max(1, int(processed.height * ratio))))
    return _run_ocr(processed).strip()


def apply_template(image, zones, user_tags=None):
    """image: PIL Image RGB brute (voir load_image), PAS encore prétraitée. zones: liste de
    dicts au format ReceiptTemplates.zones. Recadre puis OCRise CHAQUE zone séparément — plus
    fiable qu'une lecture pleine page sur un ticket dont on connaît déjà la mise en page (moins de
    bruit, résolution effective plus grande sur la zone qui compte). Même format de retour que
    parse_receipt(), plus 'zones_used' (labels du gabarit réellement présents)."""
    merchant = None
    date_found = None
    total_found = None
    items = []
    zones_used = []

    for zone in zones:
        label = zone.get('label')
        if label not in TEMPLATE_ZONE_LABELS:
            continue
        cropped = _crop_zone(image, zone)
        zones_used.append(label)

        if label == 'marchand':
            text = _ocr_zone(cropped)
            merchant = next((l.strip() for l in text.splitlines() if l.strip()), None)
        elif label == 'date':
            text = _ocr_zone(cropped)
            m = DATE_RE.search(text)
            if m:
                day, month, year = m.groups()
                if len(year) == 2:
                    year = '20' + year
                try:
                    date_found = f"{year}-{int(month):02d}-{int(day):02d}"
                except ValueError:
                    date_found = None
        elif label == 'total':
            text = _ocr_zone(cropped)
            matches = list(PRICE_RE.finditer(text))
            if matches:
                total_found = float(matches[-1].group().replace(',', '.'))
        elif label == 'articles':
            text = _ocr_zone(cropped)
            lines_raw = [l.strip() for l in text.splitlines() if l.strip()]
            items, zone_total = _parse_item_lines(lines_raw, user_tags)
            if total_found is None:
                total_found = zone_total

    warnings = []
    if total_found is not None and items:
        items_sum = round(sum(i['amount'] for i in items), 2)
        if abs(items_sum - total_found) > 0.01:
            warnings.append(
                f"La somme des lignes détectées ({items_sum}) ne correspond pas au total lu sur le ticket ({total_found}) — vérifie les lignes avant de valider."
            )
    if 'articles' in zones_used and not items:
        warnings.append("Aucune ligne d'article détectée dans la zone du gabarit — vérifie qu'elle couvre bien les articles sur ce ticket.")

    return {
        'merchant': merchant,
        'date': date_found,
        'total': total_found,
        'lines': items,
        'warnings': warnings,
        'zones_used': zones_used,
    }
