import io
import os
import re

TESSDATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tessdata')
_TESSERACT_WIN_DEFAULT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

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


def _looks_like_noise(line_upper):
    if '%' in line_upper:  # ligne de taux de TVA (ex: "A 5,5% 15,77 0,82 14,95")
        return True
    return any(kw in line_upper for kw in NOISE_KEYWORDS)


def _configure_tesseract():
    import pytesseract

    if not pytesseract.pytesseract.tesseract_cmd or pytesseract.pytesseract.tesseract_cmd == 'tesseract':
        if os.path.isfile(_TESSERACT_WIN_DEFAULT):
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT_WIN_DEFAULT
    return pytesseract


def _ocr_config():
    # Notre pack de langue française est stocké localement (backend/tessdata) plutôt que dans
    # Program Files, pour ne pas nécessiter de droits admin à l'installation.
    # --psm 4 (colonne de texte de tailles variables) donne un résultat plus stable que le mode
    # automatique par défaut sur les tickets de caisse (articles + colonnes de prix).
    return f'--tessdata-dir {TESSDATA_DIR} --psm 4'


def _preprocess(image):
    """Niveaux de gris + étirement du contraste : améliore la lecture des tickets thermiques
    pâles ou photographiés avec un éclairage inégal."""
    from PIL import ImageOps
    return ImageOps.autocontrast(ImageOps.grayscale(image))


def extract_text(file_bytes, mime_type):
    """Retourne le texte brut lu par OCR (images) ou extrait/OCRisé (PDF)."""
    pytesseract = _configure_tesseract()
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
                text = pytesseract.image_to_string(image, lang='fra', config=_ocr_config())
            pages_text.append(text)
        return '\n'.join(pages_text)

    image = _preprocess(Image.open(io.BytesIO(file_bytes)))
    return pytesseract.image_to_string(image, lang='fra', config=_ocr_config())


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
