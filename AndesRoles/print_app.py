from flask import Flask
import requests

app = Flask(__name__)

@app.route('/print_payload', methods=['POST'])
def print_payload():
    payload = requests.get_json()  # Get the JSON payload
    print("Received Payload:", payload)  # Print to console
    return {"message": "Payload received", "data": payload}, 200


if __name__ == '__main__':
    # Change '0.0.0.0' to the specific IP you want to bind
    HOST = "0.0.0.0"  # This will allow access from any device in the network
    PORT = 5000  # You can change this if needed

    app.run(host=HOST, port=PORT, debug=False)