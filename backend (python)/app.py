from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config as flask_config

app = Flask(__name__)
CORS(app)  # Ajout de cette ligne pour permettre les requêtes CORS
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://dcantau:dcantau@localhost/test'
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.from_object(flask_config)
db = SQLAlchemy(app)

class Virement(db.Model):
    __tablename__ = 'virement_temp'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    date_prod = db.Column(db.Date)
    montant = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255))

@app.route('/api/virements', methods=['GET'])
def get_virements():
    virements = Virement.query.all()
    return jsonify([{'id': virement.id, 'type': virement.type, 'date_prod': virement.date_prod, 'montant': virement.montant, 'description': virement.description} for virement in virements])

@app.route('/api/virements/<id>', methods=['DELETE'])
def delete_virement(id):
    virement = Virement.query.get(id)
    if virement:
        db.session.delete(virement)
        db.session.commit()
        return jsonify({'message': 'Virement deteted successfully'}), 200
    else:
        return jsonify({'message': 'Virement not found'}), 404

@app.route('/api/virements/<id>', methods=['PUT'])
def modify_virement(id):
    virement = Virement.query.get(id)
    if virement:
        id = request.json.get('id', virement.id)
        virement.id = id
        type = request.json.get('type', virement.type)
        virement.type = type
        date_prod = request.json.get('date_prod', virement.date_prod)
        virement.date_prod = date_prod
        montant = request.json.get('montant', virement.montant)
        virement.montant = montant
        description = request.json.get('description', virement.description)
        virement.description = description
        db.session.commit()
        return jsonify({'message': 'Virement modified successfully'}), 200
    else:
        return jsonify({'message': 'Virement not found'}), 404

@app.route('/api/virements', methods=['POST'])
def add_virement():
    type = request.json.get('type')
    date_prod = request.json.get('date_prod')
    montant = request.json.get('montant')
    description = request.json.get('description')
    virement = Virement(type=type, date_prod=date_prod, montant=montant, description=description)
    db.session.add(virement)
    db.session.commit()
    return jsonify({
        'id': virement.id,
        'type': virement.type,
        'date_prod': virement.date_prod,
        'montant': virement.montant,
        'description': virement.description
    }), 201

if __name__ == '__main__':
    app.run(debug=True)