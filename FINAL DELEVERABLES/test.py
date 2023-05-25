from flask import Flask, render_template, request, redirect, flash, url_for
import base64
import cv2
import pickle
import re
import numpy as np
import cvzone
from flask_login import UserMixin, login_user, login_required, logout_user, current_user, LoginManager
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

app = Flask(__name__)

# Connect to IBM DB2 database
db2_engine = create_engine("ibm_db_sa+pyodbc://username:password@hostname:port/database_name?security=SSL")
DBSession = sessionmaker(bind=db2_engine)
db2_session = DBSession()

Base = declarative_base()
app.config['SECRET_KEY'] = "my-Secret_key"
login_manager = LoginManager(app)


class Users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    password = Column(String(1000), nullable=False)

    def __repr__(self):
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return db2_session.query(Users).get(int(user_id))


@app.route("/logout", methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash("You Have Been Logged Out!")
    return redirect(url_for('login'))


@app.route("/")
def home():
    return render_template("index.html", current_user=current_user)


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["psw"]
        user = db2_session.query(Users).filter_by(email=email, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('home'))
        else:
            msg = "Incorrect Email/password"
            return render_template('login.html', msg=msg)
    else:
        return render_template('login.html')


@app.route("/signup", methods=['GET', 'POST'])
def signup():
    msg = ''
    if request.method == 'POST':
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["psw"]
        user = db2_session.query(Users).filter_by(email=email).first()
        if user:
            return render_template('login.html', error=True)
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = "Invalid Email Address!"
        else:
            new_user = Users(name=name, email=email, password=password)
            db2_session.add(new_user)
            db2_session.commit()
            msg = "You have successfully registered!"
            redirect(url_for('login'))
    return render_template('signup.html', msg=msg)


@app.route('/liv_pred')
def liv_pred():
    cap = cv2.VideoCapture('carParkingInput.mp4')
    with open('parkingSlotPosition', 'rb') as f:
        posList = pickle.load(f)

    width, height = 107, 48

    # Set the title of the window
    cv2.setWindowTitle("Parking Slots", "Parking Slots Detection (press q to exit)")

    def checkParkingSpace(imgPro):
        spaceCounter = 0
        for pos in posList:
            x, y = pos
            imgCrop = imgPro[y:y + height, x:x + width]
            count = cv2.countNonZero(imgCrop)
            if count < 900:
                color = (0, 255, 0)
                thickness = 5
                spaceCounter += 1
            else:
                color = (0, 0, 255)
                thickness = 2

            cv2.rectangle(img, pos, (pos[0] + width, pos[1] + height), color, thickness)

        cvzone.putTextRect(img, f'Free: {spaceCounter}/{len(posList)}', (100, 50), scale=3, thickness=5, offset=20,
                           colorR=(0, 200, 0))

    while True:
        if cap.get(cv2.CAP_PROP_POS_FRAMES) == cap.get(cv2.CAP_PROP_FRAME_COUNT):
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        success, img = cap.read()
        imgGray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        imgBlur = cv2.GaussianBlur(imgGray, (3, 3), 1)
        imgThreshold = cv2.adaptiveThreshold(imgBlur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25,
                                             16)
        imgMedian = cv2.medianBlur(imgThreshold, 5)
        kernel = np.ones((3, 3), np.uint8)
        imgDilate = cv2.dilate(imgMedian, kernel, iterations=1)
        checkParkingSpace(imgDilate)
        cv2.imshow("Parking Slots", img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
    return redirect(url_for('home'))


if __name__ == "__main__":
    Base.metadata.create_all(db2_engine)
    app.run(debug=True)
