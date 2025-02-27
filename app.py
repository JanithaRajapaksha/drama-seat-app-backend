from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from PIL import Image, ImageDraw, ImageFont
import qrcode
import os

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 16MB limit


# Firebase setup
cred = credentials.Certificate('firebaseCred.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

TEMPLATE_PATH_1000 = os.path.join('templates', 'template_1000.png')
TEMPLATE_PATH_600 = os.path.join('templates', 'template_600.png')
TEMPLATE_PATH_400 = os.path.join('templates', 'template_400.png')
FONT_PATH = 'arial.ttf'  # Path to your font file (make sure it's accessible)
FONT_SIZE = 75

# Email config
FROM_ADDRESS = "artcircledrama@gmail.com"
EMAIL_PASSWORD = "duwi punv mffr ktbv"


def send_email(to_address, subject, body, attachment_path):
    msg = MIMEMultipart()
    msg['From'] = FROM_ADDRESS
    msg['To'] = to_address
    msg['Subject'] = subject

    # Attach body
    msg.attach(MIMEText(body, 'plain'))

    # Attach the ticket
    try:
        with open(attachment_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename={os.path.basename(attachment_path)}")
            msg.attach(part)

        # Send the email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(FROM_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(FROM_ADDRESS, to_address, msg.as_string())
        print(f"Email sent successfully to {to_address}")

    except Exception as e:
        print(f"Failed to send email to {to_address}. Error: {str(e)}")

    finally:
        server.quit()

def generate_ticket_with_template(email, seat, total, phoneNo, intake, indexNumber):
    try:
        seat_number = seat['seatNo']  # Extract the seat number
        seat_price = seat['price']

        # Choose the template based on seat price
        if seat_price == 1000:
            template_path = TEMPLATE_PATH_1000
        elif seat_price == 600:
            template_path = TEMPLATE_PATH_600
        elif seat_price == 400:
            template_path = TEMPLATE_PATH_400
        else:
            raise ValueError(f"Unknown seat price: {seat_price}")

        # Generate QR code with all ticket data
        ticket_data = (
            f"Email: {email}\n"
            f"Seat: {seat_number}\n"
            f"Price: Rs. {seat_price}\n"
            f"Total: Rs. {total}\n"
            f"Phone: {phoneNo}\n"
            f"Intake: {intake}\n"
            f"Index: {indexNumber}"
        )

        qr = qrcode.make(ticket_data)
        qr_path = f"temp_qr_{seat_number}.png"
        qr.save(qr_path)

        # Load the chosen ticket template
        template = Image.open(template_path).convert('RGBA')

        # Load and resize the QR code
        qr_image = Image.open(qr_path).resize((265, 265))

        # Create a drawing context
        draw = ImageDraw.Draw(template)

        # Load the font
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

        # Define positions
        qr_position = (2000, 285)  # Adjust based on your template
        seat_number_position = (2020, 40)  # Adjust where you want the seat number

        # Draw only the seat number on the ticket
        draw.text(seat_number_position, seat_number, fill='black', font=font)

        # Paste the QR code onto the template
        template.paste(qr_image, qr_position, qr_image.convert('RGBA'))

        # Save the final ticket
        ticket_path = os.path.join('tickets', f"ticket_{seat_number}.png")
        template.save(ticket_path)

        # Cleanup QR code image
        os.remove(qr_path)

        print(f"Ticket generated: {ticket_path}")

        # Send ticket via email
        send_email(
            to_address=email,
            subject="Your Drama E-Ticket",
            body=f"""Step into the Magic with Lily’s Magic World!✨🎭  

Get ready for an enchanting theatrical experience filled with adventure, fantasy, and mesmerizing performances!  

Save the Date:
📅 11th March 2024  
⏰ 2:30 PM & 3:30 PM  
📍 KDU FGS Auditorium  

🎫 Don’t forget your E-ticket at the entrance – your QR code is your pass!  

Only E-tickets sent through our official contacts will be accepted.  
We can’t wait to take you on this magical journey!  

-Organizing Committee, Lily’s Magic World-

📞 For inquiries, contact:
- Nimshi: +94 71 524 6350  
- Sunera: +94 77 509 1029  
- Iresh: +94 71 316 5925  

(This is a computer-generated message. Do not reply.)""",
            attachment_path=ticket_path
        )

    except Exception as e:
        print(f"Failed to generate ticket for seat {seat_number}: {e}")




@app.route('/book-seats', methods=['POST'])
def book_seats():
    data = request.json
    timestamp = data.get('timestamp')
    email = data.get('email')
    seats = data.get('seats')
    total = data.get('total')
    admin = data.get('admin')
    phoneNo = data.get('phoneNo')
    intake = data.get('intake')
    indexNumber = data.get('indexNumber')

    if not email or not seats:
        return jsonify({'error': 'Invalid data'}), 400

    try:
        # Check if there are existing seat requests for the email
        seat_requests = db.collection('seat_requests').where('email', '==', email).stream()

        # If a seat request exists, remove it from the 'seat_requests' collection
        for seat_request in seat_requests:
            seat_request.reference.delete()  # Remove the document from seat_requests

        print(f"Seat request for {email} removed from 'seat_requests'.")

        # Firestore collection: 'bookings'
        booking_data = {
            'timestamp': timestamp,
            'email': email,
            'seats': seats,
            'total': total,
            'admin': admin,
            'phoneNo': phoneNo,
            'intake': intake,
            'indexNumber': indexNumber
        }

        # Add booking data to Firestore
        db.collection('bookings').add(booking_data)

        for seat in seats:
            generate_ticket_with_template(email, seat, total, phoneNo, intake, indexNumber)

        print(f"Booking confirmed for {email} by admin: {admin}")
        print(f"Timestamp: {timestamp}")
        print(f"Seats: {seats}")
        print(f"Total: Rs. {total}")
        print(f"Phone No: {phoneNo}")
        print(f"Intake: {intake}")
        print(f"Index Number: {indexNumber}")
        return jsonify({'message': 'Booking successful! E-ticket will be sent shortly.'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Failed to save booking data'}), 500


# New route to get booked seat numbers
@app.route('/booked-seats', methods=['GET'])
def get_booked_seats():
    try:
        bookings = db.collection('bookings').stream()
        booked_seats = []

        for booking in bookings:
            data = booking.to_dict()
            seats = data.get('seats', [])  # Assuming 'seats' is a list of dicts like [{'seatNo': 'H16', 'price': 400}]
            seat_numbers = [seat['seatNo'] for seat in seats]  # Extract only 'seatNo'
            booked_seats.extend(seat_numbers)  # Combine into one flat list

        print(booked_seats)
        return jsonify({'bookedSeats': booked_seats})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Failed to fetch booked seats'}), 500

@app.route('/seat-requests', methods=['GET'])
def get_seat_requests():
    try:
        # Fetch seat requests from the Firestore collection
        seat_requests = db.collection('seat_requests').stream()
        seat_request_data = []

        for request in seat_requests:
            data = request.to_dict()
            seat_request_data.append(data)  # Append each request's data to the list

        print(seat_request_data)
        return jsonify({'seatRequests': seat_request_data})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Failed to fetch seat requests'}), 500

@app.route('/request-seats', methods=['POST'])
def request_seats():
    data = request.json
    email = data.get('email')
    requested_seats = data.get('requested_seats')  # A list of dictionaries with seat details
    phoneNo = data.get('phoneNo')
    timestamp = data.get('timestamp')  # Timestamp to be received from the frontend
    reference_no = data.get('referenceNo')  # Reference number to be received from the frontend
    intake = data.get('intake')
    indexNumber = data.get('indexNumber')

    if not email or not requested_seats or not timestamp or not reference_no:
        return jsonify({'error': 'Invalid data'}), 400

    # Firestore collection: 'seat_requests'
    request_data = {
        'email': email,
        'requested_seats': requested_seats,  # Store the seat details as is (with seatNo and price)
        'phoneNo': phoneNo,
        'timestamp': timestamp,  # Add timestamp
        'referenceNo': reference_no,  # Add reference number
        'intake': intake,
        'indexNumber': indexNumber
    }

    try:
        # Save the request details to Firestore
        db.collection('seat_requests').add(request_data)
        print(f"Request received for {email}")
        print(f"Requested seats: {requested_seats}")
        print(f"Reference No: {reference_no}, Timestamp: {timestamp}")
        print(f"Phone No: {phoneNo}")
        print(f"Intake: {intake}")
        print(f"Index Number: {indexNumber}")
        return jsonify({'message': 'Seats requested successfully. Please proceed to booking.'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Failed to save seat request'}), 500






if __name__ == '__main__':
    app.run(debug=True)
