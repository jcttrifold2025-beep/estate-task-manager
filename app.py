import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import time
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import json
import threading

# Page configuration
st.set_page_config(
    page_title="Estate Task Manager",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
        margin-bottom: 1rem;
    }
    .status-completed { background-color: #d4edda; border-color: #28a745; }
    .status-delayed { background-color: #f8d7da; border-color: #dc3545; }
    .status-progress { background-color: #fff3cd; border-color: #ffc107; }
    .status-not-started { background-color: #e2e3e5; border-color: #6c757d; }
    .priority-high { background-color: #ffebee; color: #c62828; }
    .priority-medium { background-color: #fff3e0; color: #ef6c00; }
    .priority-low { background-color: #e8f5e8; color: #2e7d32; }
</style>
""", unsafe_allow_html=True)

class TaskManager:
    def __init__(self):
        self.sheet_url = st.secrets.get("SHEET_URL", "")
        self.setup_google_sheets()
        self.admin_emails = ["trifold2025@gmail.com"]
        
    def setup_google_sheets(self):
        """Initialize Google Sheets connection"""
        try:
            creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
            scope = ['https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            client = gspread.authorize(creds)
            self.sheet = client.open_by_url(self.sheet_url).sheet1
        except Exception as e:
            st.error(f"Error connecting to Google Sheets: {e}")
            
    def get_all_tasks(self):
        """Fetch all tasks from Google Sheets"""
        try:
            data = self.sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                # Convert date columns
                date_columns = ['Start Date', 'Deadline', 'Last Updated']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                return df
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Error fetching data: {e}")
            return pd.DataFrame()
            
    def update_task(self, task_id, updates):
        """Update a task in Google Sheets"""
        try:
            # Find the row with the task_id
            all_data = self.sheet.get_all_records()
            for idx, row in enumerate(all_data, start=2):  # start=2 because of header
                if str(row.get('Task ID', '')) == str(task_id):
                    for key, value in updates.items():
                        col_idx = self.get_column_index(key)
                        if col_idx:
                            if isinstance(value, datetime):
                                value = value.strftime('%Y-%m-%d')
                            self.sheet.update_cell(idx, col_idx, str(value))
                    # Update Last Updated timestamp
                    last_updated_col = self.get_column_index('Last Updated')
                    if last_updated_col:
                        self.sheet.update_cell(idx, last_updated_col, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    return True
            return False
        except Exception as e:
            st.error(f"Error updating task: {e}")
            return False
            
    def add_task(self, task_data):
        """Add a new task to Google Sheets"""
        try:
            # Generate new Task ID
            all_tasks = self.get_all_tasks()
            if not all_tasks.empty:
                new_id = int(all_tasks['Task ID'].max()) + 1
            else:
                new_id = 1
                
            task_data['Task ID'] = new_id
            task_data['Last Updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Prepare row data in correct column order
            columns = ['Task ID', 'Task Description', 'Category', 'Responsible', 
                      'Start Date', 'Deadline', 'Status', 'Priority', 'Progress %', 
                      'Remarks', 'Last Updated']
            row_data = [task_data.get(col, '') for col in columns]
            
            self.sheet.append_row(row_data)
            return True
        except Exception as e:
            st.error(f"Error adding task: {e}")
            return False
            
    def get_column_index(self, column_name):
        """Get column index by name"""
        headers = self.sheet.row_values(1)
        try:
            return headers.index(column_name) + 1
        except ValueError:
            return None

def authenticate_user():
    """Simple email-based authentication"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_email = ""
        st.session_state.user_role = ""
        
    if not st.session_state.authenticated:
        st.title("🔐 Estate Task Manager - Login")
        
        with st.form("login_form"):
            email = st.text_input("Email Address", placeholder="Enter your email address")
            submit = st.form_submit_button("Login")
            
            if submit:
                if "@" in email and "." in email:
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    if email in task_manager.admin_emails:
                        st.session_state.user_role = "Admin"
                    else:
                        st.session_state.user_role = "Viewer"
                    st.rerun()
                else:
                    st.error("Please enter a valid email address")
        return False
    return True

def create_dashboard(df):
    """Create the main dashboard"""
    st.markdown('<div class="main-header">🏢 Estate Task Manager – [College Name]</div>', unsafe_allow_html=True)
    
    # Dashboard metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_tasks = len(df)
        st.metric("Total Tasks", total_tasks)
        
    with col2:
        overdue_tasks = len(df[(df['Deadline'] < datetime.now().date()) & (df['Status'] != 'Completed')])
        st.metric("Overdue Tasks", overdue_tasks, delta=f"-{overdue_tasks} urgent")
        
    with col3:
        upcoming_deadlines = len(df[(df['Deadline'] <= datetime.now().date() + timedelta(days=7)) & 
                                  (df['Deadline'] >= datetime.now().date())])
        st.metric("Upcoming (7 days)", upcoming_deadlines)
        
    with col4:
        if not df.empty and 'Progress %' in df.columns:
            overall_progress = df['Progress %'].mean()
            st.metric("Overall Progress", f"{overall_progress:.1f}%")
        else:
            st.metric("Overall Progress", "0%")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        if not df.empty and 'Category' in df.columns:
            category_counts = df['Category'].value_counts()
            fig = px.pie(values=category_counts.values, names=category_counts.index, 
                        title="Tasks by Category")
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        if not df.empty and 'Status' in df.columns:
            status_counts = df['Status'].value_counts()
            fig = px.bar(x=status_counts.index, y=status_counts.values,
                        title="Tasks by Status", color=status_counts.index,
                        color_discrete_map={
                            'Completed': '#28a745',
                            'In Progress': '#ffc107', 
                            'Not Started': '#6c757d',
                            'Delayed': '#dc3545'
                        })
            st.plotly_chart(fig, use_container_width=True)
    
    # Workload by Responsible Person
    if not df.empty and 'Responsible' in df.columns:
        st.subheader("Workload by Responsible Person")
        workload = df['Responsible'].value_counts()
        fig = px.bar(x=workload.index, y=workload.values, title="Tasks per Person")
        st.plotly_chart(fig, use_container_width=True)

def show_all_tasks(df):
    """Display all tasks in a table with filters"""
    st.header("📋 All Tasks")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_filter = st.multiselect("Status", options=df['Status'].unique() if not df.empty else [])
    with col2:
        category_filter = st.multiselect("Category", options=df['Category'].unique() if not df.empty else [])
    with col3:
        responsible_filter = st.multiselect("Responsible", options=df['Responsible'].unique() if not df.empty else [])
    with col4:
        priority_filter = st.multiselect("Priority", options=df['Priority'].unique() if not df.empty else [])
    
    # Apply filters
    filtered_df = df.copy()
    if status_filter:
        filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]
    if category_filter:
        filtered_df = filtered_df[filtered_df['Category'].isin(category_filter)]
    if responsible_filter:
        filtered_df = filtered_df[filtered_df['Responsible'].isin(responsible_filter)]
    if priority_filter:
        filtered_df = filtered_df[filtered_df['Priority'].isin(priority_filter)]
    
    # Search
    search_term = st.text_input("🔍 Search tasks...")
    if search_term:
        filtered_df = filtered_df[filtered_df['Task Description'].str.contains(search_term, case=False, na=False)]
    
    # Display table
    if not filtered_df.empty:
        display_df = filtered_df.copy()
        # Format dates for display
        date_columns = ['Start Date', 'Deadline', 'Last Updated']
        for col in date_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col].dt.strftime('%Y-%m-%d')
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No tasks found matching the filters.")

def show_kanban_view(df):
    """Display tasks in Kanban view"""
    st.header("📋 Kanban View")
    
    if df.empty:
        st.info("No tasks available.")
        return
        
    status_columns = ['Not Started', 'In Progress', 'Completed', 'Delayed']
    
    cols = st.columns(len(status_columns))
    
    for idx, status in enumerate(status_columns):
        with cols[idx]:
            st.subheader(status)
            status_tasks = df[df['Status'] == status]
            
            for _, task in status_tasks.iterrows():
                with st.container():
                    st.markdown(f"""
                    <div class="metric-card status-{status.lower().replace(' ', '-')}">
                        <strong>{task['Task Description']}</strong><br>
                        📅 {task['Deadline'].strftime('%Y-%m-%d') if pd.notna(task['Deadline']) else 'No deadline'}<br>
                        👤 {task['Responsible']}<br>
                        📊 Progress: {task.get('Progress %', 0)}%
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.session_state.user_role == "Admin":
                        if st.button(f"Edit", key=f"edit_{task['Task ID']}"):
                            st.session_state.editing_task = task['Task ID']
                        if st.button("Delete", key=f"delete_{task['Task ID']}"):
                            if task_manager.update_task(task['Task ID'], {'Status': 'Deleted'}):
                                st.success("Task deleted!")
                                st.rerun()

def show_calendar_view(df):
    """Display tasks in calendar view"""
    st.header("📅 Calendar View")
    
    if df.empty:
        st.info("No tasks available.")
        return
        
    # Create a calendar-like view
    today = datetime.now().date()
    week_dates = [today + timedelta(days=i) for i in range(7)]
    
    cols = st.columns(7)
    
    for idx, date in enumerate(week_dates):
        with cols[idx]:
            st.subheader(date.strftime('%a\n%m/%d'))
            day_tasks = df[df['Deadline'].dt.date == date]
            
            for _, task in day_tasks.iterrows():
                priority_color = {
                    'High': 'priority-high',
                    'Medium': 'priority-medium', 
                    'Low': 'priority-low'
                }.get(task['Priority'], '')
                
                st.markdown(f"""
                <div class="metric-card {priority_color}">
                    <small><strong>{task['Task Description']}</strong></small><br>
                    <small>👤 {task['Responsible']}</small><br>
                    <small>📊 {task.get('Progress %', 0)}%</small>
                </div>
                """, unsafe_allow_html=True)

def add_task_form():
    """Form to add new task (Admin only)"""
    st.header("➕ Add New Task")
    
    with st.form("add_task_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            task_desc = st.text_area("Task Description")
            category = st.text_input("Category")
            responsible = st.text_input("Responsible Person")
            start_date = st.date_input("Start Date", datetime.now())
            
        with col2:
            deadline = st.date_input("Deadline", datetime.now() + timedelta(days=7))
            status = st.selectbox("Status", ["Not Started", "In Progress", "Completed", "Delayed"])
            priority = st.selectbox("Priority", ["High", "Medium", "Low"])
            progress = st.slider("Progress %", 0, 100, 0)
            remarks = st.text_area("Remarks")
        
        submitted = st.form_submit_button("Add Task")
        
        if submitted:
            if task_desc and responsible:
                task_data = {
                    'Task Description': task_desc,
                    'Category': category,
                    'Responsible': responsible,
                    'Start Date': start_date.strftime('%Y-%m-%d'),
                    'Deadline': deadline.strftime('%Y-%m-%d'),
                    'Status': status,
                    'Priority': priority,
                    'Progress %': progress,
                    'Remarks': remarks
                }
                
                if task_manager.add_task(task_data):
                    st.success("Task added successfully!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("Please fill in required fields: Task Description and Responsible Person")

def main():
    # Initialize task manager
    global task_manager
    task_manager = TaskManager()
    
    # Authenticate user
    if not authenticate_user():
        return
        
    # Welcome message
    st.sidebar.success(f"Logged in as: {st.session_state.user_email} ({st.session_state.user_role})")
    
    # Navigation
    st.sidebar.title("Navigation")
    app_mode = st.sidebar.selectbox("Choose a view", 
                                   ["Dashboard", "All Tasks", "Kanban View", "Calendar View"])
    
    if st.session_state.user_role == "Admin":
        if st.sidebar.button("➕ Add New Task"):
            st.session_state.show_add_task = True
    
    # Auto-refresh
    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()
    
    # Load data
    df = task_manager.get_all_tasks()
    
    # Show appropriate view
    if app_mode == "Dashboard":
        create_dashboard(df)
    elif app_mode == "All Tasks":
        show_all_tasks(df)
    elif app_mode == "Kanban View":
        show_kanban_view(df)
    elif app_mode == "Calendar View":
        show_calendar_view(df)
    
    # Show add task form if requested
    if st.session_state.get('show_add_task', False) and st.session_state.user_role == "Admin":
        add_task_form()
        if st.button("Back to Main View"):
            st.session_state.show_add_task = False
            st.rerun()

if __name__ == "__main__":
    main()