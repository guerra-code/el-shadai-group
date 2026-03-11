import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
from supabase import create_client, Client
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import hashlib

# ================= PAGE CONFIG =================
st.set_page_config(page_title="EL SHADAI ENTERPRISE PRO", layout="wide")

# ================= DARK LUXURY STYLE =================
st.markdown("""
<style>
/* ===== Global Background & Text ===== */
html, body, [class*="css"] {
    background-color: #0d1b40; /* deep royal blue */
    color: #f0e6d2; /* soft creamy text */
    font-family: 'Inter', sans-serif;
}

/* ===== Headings ===== */
h1, h2, h3 {
    font-family: 'Playfair Display', serif;
    color: #000000; /* black headings */
    margin-bottom: 10px;
}

/* ===== Sidebar ===== */
section[data-testid="stSidebar"] {
    background-color: #102454 !important;
    border-right: 1px solid #1f2e5c;
    padding: 10px;
}
section[data-testid="stSidebar"] * {
    color: #f0e6d2 !important;
    font-weight: 400;
}

/* ===== Buttons ===== */
.stButton>button {
    background-color: #000000 !important;
    color: #f0e6d2 !important;
    font-weight: 500;
    border-radius: 8px;
    border: none;
    padding: 6px 14px;
    transition: 0.2s ease;
}
.stButton>button:hover {
    background-color: #222222 !important;
    transform: scale(1.03);
}

/* ===== Inputs / Selectboxes Clean Flat ===== */
.stTextInput, .stNumberInput, .stSelectbox {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    box-shadow: none !important;
}

/* All input text black (login, register, inventory, sales, etc.) */
.stTextInput>div>div input,
.stNumberInput>div>div input,
.stSelectbox>div>div span {
    color: #000000 !important; /* black text everywhere */
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Dropdown options text black */
div[role="listbox"] div[role="option"] {
    color: #000000 !important;
    background-color: #f0e6d2 !important; /* light background for readability */
}
div[role="listbox"] div[role="option"]:hover {
    background-color: #dcd6c5 !important;
}

/* Remove inner shadows / container effects */
.css-1d391kg, .css-1v3fvcr {
    background: none !important;
    box-shadow: none !important;
}

/* Metric Cards */
.metric-card {
    background: rgba(0,0,0,0.08);
    padding: 18px;
    border-radius: 12px;
    border: 1px solid rgba(0,0,0,0.25);
    text-align: center;
    font-weight: 500;
    color: #f0e6d2;
}

/* Low stock highlight */
.low-stock {
    background-color: #b84b4b !important;
    color: #fff !important;
    font-weight: 600;
}

/* Tables clean look */
.stDataFrame div[data-testid="stHorizontalBlock"] {
    background-color: #0d1b40;
    color: #f0e6d2;
}
.stDataFrame td {
    border-bottom: 1px solid #1f2e5c;
}

/* Minor adjustments */
div.css-1d391kg {
    color: #f0e6d2;
}
</style>
""", unsafe_allow_html=True)# ================= SUPABASE =================
SUPABASE_URL = "https://hbsmtddphxoayqxzestu.supabase.co"
SUPABASE_KEY = "sb_publishable_IkrQv7UU1AAlp69IkyNCpg_E3OO---i" 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= LANGUAGE =================
if "lang" not in st.session_state:
    st.session_state.lang = "EN"

def t(en, rw):
    return en if st.session_state.lang == "EN" else rw

lang_choice = st.sidebar.selectbox("Language / Ururimi", ["English","Kinyarwanda"])
st.session_state.lang = "EN" if lang_choice=="English" else "RW"

# ================= CURRENCY =================
currency_map = {
    "Rwanda": "RWF",
    "Kenya": "KES",
    "Uganda": "UGX",
    "Tanzania": "TZS",
    "USA": "$"
}

# ================= SESSION =================
for key in ["logged_in","user","role","store","country","user_id"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ================= HELPERS =================
def load_table(name):
    res = supabase.table(name).select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

def get_user_inventory():
    inv = load_table("inventory")
    if inv.empty:
        return pd.DataFrame()
    return inv[
        (inv["user_id"]==st.session_state.user_id) &
        (inv["store"]==st.session_state.store) &
        (inv["country"]==st.session_state.country)
    ]

def get_user_sales():
    sales = load_table("sales")
    if sales.empty:
        return pd.DataFrame()
    return sales[
        (sales["user_id"]==st.session_state.user_id) &
        (sales["store"]==st.session_state.store) &
        (sales["country"]==st.session_state.country)
    ]

def upsert_inventory(df):
    """
    Manual UPSERT: If product exists, add stock; else insert
    """
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        row_dict["user_id"] = int(row_dict["user_id"])
        existing = supabase.table("inventory").select("*").eq("user_id", row_dict["user_id"])\
                    .eq("store", row_dict["store"]).eq("country", row_dict["country"])\
                    .eq("product", row_dict["product"]).execute()
        if existing.data:
            old_stock = existing.data[0]["total_stock"]
            row_dict["total_stock"] += old_stock
            supabase.table("inventory").update(row_dict).eq("id", existing.data[0]["id"]).execute()
        else:
            supabase.table("inventory").insert(row_dict).execute()

def insert_sales(df):
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        if "date" in row_dict:
            if hasattr(row_dict["date"], "isoformat"):
                row_dict["date"] = row_dict["date"].isoformat()
        supabase.table("sales").insert(row_dict).execute()

def insert_user(df):
    for _, row in df.iterrows():
        # Optional: hash password
        # row["password"] = hashlib.sha256(row["password"].encode()).hexdigest()
        supabase.table("users").insert(row.to_dict()).execute()

def generate_receipt(sale_df):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    style = getSampleStyleSheet()
    elements.append(Paragraph("EL SHADAI ENTERPRISE RECEIPT", style["Title"]))
    data = [list(sale_df.columns)] + sale_df.values.tolist()
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.gold),
        ('GRID', (0,0), (-1,-1), 1, colors.white),
        ('BACKGROUND', (0,1), (-1,-1), colors.black),
        ('TEXTCOLOR',(0,1),(-1,-1),colors.white)
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ================= LOGIN =================
def login(u,p):
    users = load_table("users")
    # Optional: hash password for check
    # p = hashlib.sha256(p.encode()).hexdigest()
    match = users[(users["username"]==u) & (users["password"]==p)]
    if not match.empty:
        row = match.iloc[0]
        st.session_state.user=row["username"]
        st.session_state.role=row.get("role","user")
        st.session_state.store=row["store"]
        st.session_state.country=row["country"]
        st.session_state.user_id=row["id"]
        return True
    return False

# ================= AUTH =================
if not st.session_state.logged_in:
    st.title("EL SHADAI ENTERPRISE")
    tab1, tab2 = st.tabs([t("Login","Injira"), t("Register","Iyandikishe")])

    with tab1:
        u = st.text_input(t("Username","Izina ry'ukoresha"), key="login_user")
        p = st.text_input(t("Password","Ijambo banga"), type="password", key="login_pass")
        if st.button(t("Login","Injira")):
            if login(u,p):
                st.session_state.logged_in=True
                st.rerun()
            else:
                st.error(t("Invalid credentials","Amakuru si yo"))

    with tab2:
        new_u = st.text_input(t("Username","Izina ry'ukoresha"), key="reg_user")
        new_p = st.text_input(t("Password","Ijambo banga"), type="password", key="reg_pass")
        new_store = st.text_input(t("Store","Izina ry'iduka"), key="reg_store")
        new_country = st.selectbox(t("Country","Igihugu"), list(currency_map.keys()), key="reg_country")
        if st.button(t("Register","Iyandikishe")):
            df = pd.DataFrame([{
                "username":new_u,
                "password":new_p,
                "store":new_store,
                "country":new_country,
                "role":"user"
            }])
            insert_user(df)
            st.success(t("Registered Successfully","Kwiyandikisha byagenze neza"))

else:
    currency = currency_map.get(st.session_state.country,"")

    st.sidebar.markdown(f"👤 {st.session_state.user}")
    st.sidebar.markdown(f"🏬 {st.session_state.store}")
    st.sidebar.markdown(f"🌍 {st.session_state.country}")

    if st.sidebar.button(t("Logout","Sohoka")):
        st.session_state.logged_in=False
        st.rerun()

    page = st.sidebar.radio(t("Navigation","Imiyoborere"),
                            [t("Dashboard","Ahabanza"),
                             t("Inventory","Ububiko"),
                             t("Sales","Igurisha"),
                             t("Reports","Raporo")])

    user_inventory = get_user_inventory()
    user_sales = get_user_sales()

    # ================= DASHBOARD =================
    if page==t("Dashboard","Ahabanza"):
        st.title(t("Executive Dashboard","Imbonerahamwe Nyobozi"))
        revenue = user_sales["total"].sum() if not user_sales.empty else 0
        profit = user_sales["profit"].sum() if not user_sales.empty else 0
        low_stock_count = len(user_inventory[user_inventory["total_stock"] < 5]) if not user_inventory.empty else 0
        col1, col2, col3 = st.columns(3)
        col1.metric(t("Revenue","Amafaranga yinjira"), f"{currency} {revenue:,.0f}")
        col2.metric(t("Profit","Inyungu"), f"{currency} {profit:,.0f}")
        col3.metric(t("Low Stock Items","Ibicuruzwa bike"), low_stock_count)

    # ================= INVENTORY =================
    elif page==t("Inventory","Ububiko"):
        st.title(t("Inventory Management","Imicungire y'Ububiko"))

        with st.form("multi_product"):
            count = st.number_input(t("Number of products to add","Umubare w'ibicuruzwa byo kongeramo"), min_value=1, max_value=20, value=1)
            products = []
            for i in range(int(count)):
                st.markdown(f"### Product {i+1}")
                name = st.text_input(t("Product Name","Izina ry'Igicuruzwa"), key=f"name{i}")
                unit = st.selectbox(t("Unit","Igipimo"), ["kg","g","L","ml","pcs"], key=f"unit{i}")
                containers = st.number_input(t("Containers","Agasanduku"), min_value=1.0, key=f"cont{i}")
                amount = st.number_input(t("Amount per container","Ingano mu Gasanduku"), min_value=1.0, key=f"amt{i}")
                cost = st.number_input(t("Cost per unit","Igiciro ku gipimo"), min_value=0.0, key=f"cost{i}")
                price = st.number_input(t("Selling price per unit","Igiciro cyo kugurisha"), min_value=0.0, key=f"price{i}")
                total_stock = containers * amount
                products.append({
                    "user_id": st.session_state.user_id,
                    "store": st.session_state.store,
                    "country": st.session_state.country,
                    "product": name,
                    "total_stock": total_stock,
                    "selling_unit": unit,
                    "container_type": "General",
                    "amount_per_container": amount,
                    "cost_price": cost,
                    "selling_price": price
                })
            if st.form_submit_button(t("Save Products","Bika ibicuruzwa")):
                df = pd.DataFrame(products)
                upsert_inventory(df)
                st.success(t("Products saved successfully","Ibicuruzwa byabitswe neza"))
                st.rerun()

        if not user_inventory.empty:
            def highlight(row):
                return ['low-stock' if row['total_stock'] < 5 else '' for _ in row]
            st.dataframe(user_inventory.style.apply(highlight, axis=1))

    # ================= SALES =================
    elif page==t("Sales","Igurisha"):
        st.title(t("Sales Entry","Kwandika Igurisha"))
        if not user_inventory.empty:
            product = st.selectbox(t("Product","Igicuruzwa"), user_inventory["product"])
            row = user_inventory[user_inventory["product"]==product].iloc[0]
            available = float(row["total_stock"])
            st.write(f"{t('Available','Bihari')}: {available} {row['selling_unit']}")
            qty = st.number_input(t("Quantity to sell","Umubare wo kugurisha"), min_value=0.01, max_value=available)
            if st.button(t("Record Sale","Andika Igurisha")):
                total = qty * float(row["selling_price"])
                profit = (float(row["selling_price"]) - float(row["cost_price"])) * qty
                sale_df = pd.DataFrame([{
                    "user_id": st.session_state.user_id,
                    "store": st.session_state.store,
                    "country": st.session_state.country,
                    "date": datetime.now().isoformat(),
                    "product": product,
                    "quantity": qty,
                    "unit_price": row["selling_price"],
                    "total": total,
                    "profit": profit
                }])
                insert_sales(sale_df)
                # update inventory
                new_stock = available - qty
                inv_df = pd.DataFrame([{
                    "user_id": st.session_state.user_id,
                    "store": st.session_state.store,
                    "country": st.session_state.country,
                    "product": product,
                    "total_stock": new_stock,
                    "selling_unit": row["selling_unit"],
                    "container_type": row["container_type"],
                    "amount_per_container": row["amount_per_container"],
                    "cost_price": row["cost_price"],
                    "selling_price": row["selling_price"]
                }])
                upsert_inventory(inv_df)
                st.success(t("Sale recorded","Igurisha ryanditswe"))
                pdf = generate_receipt(sale_df)
                st.download_button(t("Download Receipt","Kuramo Receipt"), pdf, file_name="receipt.pdf")
                st.rerun()

    # ================= REPORTS =================
    elif page==t("Reports","Raporo"):
        st.title(t("Financial Reports","Raporo y'Imari"))
        if not user_sales.empty:
            fig = px.line(user_sales, x="date", y="total", title=t("Total Sales Over Time","Igurisha Ryose mu Gihe"))
            st.plotly_chart(fig)
            st.dataframe(user_sales)
