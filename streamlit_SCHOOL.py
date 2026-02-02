import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

st.set_page_config(page_title="School SMS", layout="wide")

# ------------------- Database -------------------
def init_db():
    conn = sqlite3.connect("school.db", check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, name TEXT, class TEXT, contact TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS finances (id INTEGER PRIMARY KEY, type TEXT, category TEXT, amount REAL, date TEXT, description TEXT)''')
    # Create default admin
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("admin", "admin123"))
    conn.commit()
    conn.close()

init_db()

# ------------------- Session State -------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# ------------------- Login Page -------------------
def login_page():
    st.title("School Management System")
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = sqlite3.connect("school.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        if c.fetchone():
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success("Login successful!")
            st.rerun()
        else:
            st.error("Wrong username or password")
        conn.close()

# ------------------- Main App -------------------
if not st.session_state.logged_in:
    login_page()
else:
    st.sidebar.title(f"Welcome, {st.session_state.username}")
    page = st.sidebar.radio("Go to", ["Dashboard", "Students", "Finances", "Reports"])

    conn = sqlite3.connect("school.db", check_same_thread=False)

    if page == "Dashboard":
        st.title("Dashboard")
        st.write("Quick overview of your school")
        col1, col2, col3 = st.columns(3)
        students_count = pd.read_sql("SELECT COUNT(*) as count FROM students", conn).iloc[0]['count']
        income = pd.read_sql("SELECT SUM(amount) as total FROM finances WHERE type='Income'", conn).iloc[0]['total'] or 0
        expense = pd.read_sql("SELECT SUM(amount) as total FROM finances WHERE type='Expense'", conn).iloc[0]['total'] or 0
        col1.metric("Total Students", students_count)
        col2.metric("Total Income", f"UGX {income:,.0f}")
        col3.metric("Total Expenses", f"UGX {expense:,.0f}")

    elif page == "Students":
        st.title("Students")
        with st.form("add_student"):
            name = st.text_input("Full Name")
            class_name = st.text_input("Class")
            contact = st.text_input("Contact (Phone/Email)")
            submitted = st.form_submit_button("Add Student")
            if submitted and name:
                c = conn.cursor()
                c.execute("INSERT INTO students (name, class, contact) VALUES (?, ?, ?)", (name, class_name, contact))
                conn.commit()
                st.success("Student added!")
        df = pd.read_sql("SELECT * FROM students", conn)
        st.dataframe(df, use_container_width=True)

    elif page == "Finances":
        st.title("Incomes & Expenses")
        with st.form("add_finance"):
            type_ = st.selectbox("Type", ["Income", "Expense"])
            category = st.selectbox("Category", ["Fees", "Donations", "Salaries", "Utilities", "Supplies", "Other"])
            amount = st.number_input("Amount (UGX)", min_value=0.0)
            date_ = st.date_input("Date", date.today())
            description = st.text_input("Description")
            submitted = st.form_submit_button("Save")
            if submitted:
                c = conn.cursor()
                c.execute("INSERT INTO finances (type, category, amount, date, description) VALUES (?, ?, ?, ?, ?)",
                          (type_, category, amount, str(date_), description))
                conn.commit()
                st.success("Record saved!")
        df = pd.read_sql("SELECT * FROM finances ORDER BY date DESC", conn)
        st.dataframe(df, use_container_width=True)

    elif page == "Reports":
        st.title("Financial Reports")
        year = st.number_input("Year", min_value=2020, max_value=2030, value=2025)
        df = pd.read_sql(f"SELECT * FROM finances WHERE date LIKE '{year}%'", conn)
        
        income = df[df['type']=='Income']['amount'].sum()
        expense = df[df['type']=='Expense']['amount'].sum()
        st.metric("Total Income", f"UGX {income:,.0f}")
        st.metric("Total Expenses", f"UGX {expense:,.0f}")
        st.metric("Net Balance", f"UGX {income-expense:,.0f}")
        
        st.subheader("Breakdown by Category")
        st.dataframe(df.groupby(['type','category'])['amount'].sum().reset_index())

        # Download buttons
        col1, col2 = st.columns(2)
        if col1.button("Download PDF"):
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            p.drawString(100, 750, f"School Financial Report - {year}")
            p.drawString(100, 730, f"Income: UGX {income:,.0f}")
            p.drawString(100, 710, f"Expenses: UGX {expense:,.0f}")
            p.drawString(100, 690, f"Net: UGX {income-expense:,.0f}")
            p.save()
            buffer.seek(0)
            st.download_button("Download PDF", buffer, f"report_{year}.pdf", "application/pdf")
        
        if col2.button("Download Excel"):
            wb = Workbook()
            ws = wb.active
            ws.title = "Finances"
            for r in pd.DataFrame(df).itertuples(index=False):
                ws.append(r)
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            st.download_button("Download Excel", buffer, f"report_{year}.xlsx", 
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    conn.close()

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
