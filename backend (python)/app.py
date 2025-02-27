from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Ajout de cette ligne pour permettre les requêtes CORS
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://dcantau:dcantau@localhost/test'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Virement(db.Model):
    __tablename__ = 'virement'
    id = db.Column(db.String(5), primary_key=True)
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
        return jsonify({'message': 'Virement deleted successfully'}), 200
    else:
        return jsonify({'message': 'Virement not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)