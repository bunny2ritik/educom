import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import re
import json
import io
from typing import Dict, List, Tuple, Any

# Configure page
st.set_page_config(
    page_title="Eduroam User Movement Analytics",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .logo-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        padding: 15px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #2a5298;
        margin: 10px 0;
    }
    
    .user-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin: 10px 0;
    }
    
    .foreign-user {
        border-left: 4px solid #dc3545;
        background: #fff5f5;
    }
    
    .indian-user {
        border-left: 4px solid #28a745;
        background: #f5fff5;
    }
    
    .roaming-user {
        border-left: 4px solid #ffc107;
        background: #fffbf0;
    }
    
    .movement-timeline {
        background: white;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 3px solid #007bff;
    }
    
    .success-connection {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    
    .failed-connection {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    
    .filter-section {
        background: #f1f3f4;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    
    .stAlert {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

class EduroamLogAnalyzer:
    def __init__(self):
        self.processed_data = None
        self.user_movements = {}
        self.analytics_data = {}
        
        # Indian university domains/institutions
        self.indian_institutions = [
            'iitd.ac.in', 'iitm.ac.in', 'iitb.ac.in', 'iitg.ac.in', 'iitk.ac.in', 'iitr.ac.in',
            'iiserkol.ac.in', 'iisc.ac.in', 'icgeb.ac.in', 'nit.ac.in', 'ernet.in',
            'iiserpune.ac.in', 'iisertvm.ac.in', 'iiserb.ac.in', 'bits-pilani.ac.in',
            'jnu.ac.in', 'du.ac.in', 'tifr.res.in', 'cdac.in', 'csir.res.in'
        ]
        
        # Institution coordinates (approximate)
        self.institution_coordinates = {
            'iitd': [28.6139, 77.2090],      # IIT Delhi
            'iitm': [12.9716, 80.2594],      # IIT Madras
            'iitb': [19.1334, 72.9133],      # IIT Bombay
            'iitg': [26.1890, 91.6917],      # IIT Guwahati
            'iitk': [26.5123, 80.2329],      # IIT Kanpur
            'iitr': [29.8650, 77.8950],      # IIT Roorkee
            'iiserkol': [22.5726, 88.3639],  # IISER Kolkata
            'iisc': [13.0827, 77.5718],      # IISc Bangalore
            'etlr1.eduroam.org': [52.5200, 13.4050],  # Default European location
            'etlr2.eduroam.org': [55.6761, 12.5683],  # Default European location
        }
        
        # Country coordinates
        self.country_coordinates = {
            'India': [20.5937, 78.9629],
            'Italy': [41.8719, 12.5674],
            'UK': [55.3781, -3.4360],
            'USA': [39.8283, -98.5795],
            'Germany': [51.1657, 10.4515],
            'France': [46.2276, 2.2137],
            'Netherlands': [52.1326, 5.2913],
            'Sweden': [60.1282, 18.6435]
        }
    
    def parse_eduroam_log(self, log_content: str) -> pd.DataFrame:
        """Parse eduroam authentication logs"""
        lines = log_content.strip().split('\n')
        
        # Regex patterns for different log types
        access_pattern = re.compile(
            r'^(?P<timestamp>\w{3} \w{3} \d{2} \d{2}:\d{2}:\d{2} \d{4}): '
            r'Access-(?P<status>Accept|Reject)'
            r'(?: for user (?P<user>[\w.@-]+))?'
            r'(?: stationid (?P<stationid>[\w:.-]+))?'
            r'(?: cui (?P<cui>[\w]+))?'
            r'(?: from (?P<from_inst>[\w.-]+))?'
            r'(?: to (?P<to_inst>[\w.-]+))?'
            r'.*\((?P<ip>[\d.]+)\)'
            r'(?:.* operator (?P<operator>[\w.-]+))?'
        )
        
        fticks_pattern = re.compile(
            r'^(?P<timestamp>\w{3} \w{3} \d{2} \d{2}:\d{2}:\d{2} \d{4}): '
            r'F-TICKS/eduroam/[\d.]+#REALM=(?P<realm>[^#]*)#'
            r'VISCOUNTRY=(?P<viscountry>[^#]*)#'
            r'VISINST=(?P<visinst>[^#]*)#'
            r'CSI=(?P<csi>[^#]*)#'
            r'RESULT=(?P<result>[^#]*)#'
        )
        
        records = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Parse access logs
            access_match = access_pattern.match(line)
            if access_match:
                record = access_match.groupdict()
                record['log_type'] = 'access'
                records.append(record)
            
            # Parse F-TICKS logs
            fticks_match = fticks_pattern.match(line)
            if fticks_match:
                record = fticks_match.groupdict()
                record['log_type'] = 'fticks'
                records.append(record)
        
        if not records:
            st.error("No valid eduroam log entries found. Please check your log file format.")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Convert timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='%a %b %d %H:%M:%S %Y')
        
        # Clean and enrich data
        df = self.enrich_log_data(df)
        
        return df
    
    def enrich_log_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enrich log data with additional information"""
        # Fill missing values
        df['user'] = df['user'].fillna('unknown')
        df['from_inst'] = df['from_inst'].fillna('unknown')
        df['to_inst'] = df['to_inst'].fillna('unknown')
        df['realm'] = df.get('realm', df['user'].str.split('@').str[1]).fillna('')
        
        # Determine user type (Indian vs Foreign)
        def classify_user_type(user, realm, from_inst, to_inst):
            if pd.isna(realm) or realm == '':
                realm = ''
            
            # Check email domain
            if any(domain in str(realm).lower() for domain in self.indian_institutions):
                return 'Indian'
            
            # Check institution names
            inst_names = str(from_inst).lower() + ' ' + str(to_inst).lower()
            if any(iit in inst_names for iit in ['iit', 'iisc', 'iiser', 'nit']):
                return 'Indian'
            
            return 'Foreign'
        
        df['user_type'] = df.apply(
            lambda row: classify_user_type(row['user'], row['realm'], row['from_inst'], row['to_inst']),
            axis=1
        )
        
        # Determine country based on realm
        def get_country_from_realm(realm):
            if pd.isna(realm) or realm == '':
                return 'Unknown'
            
            realm = str(realm).lower()
            if '.in' in realm or any(inst in realm for inst in self.indian_institutions):
                return 'India'
            elif '.it' in realm:
                return 'Italy'
            elif '.uk' in realm or '.ac.uk' in realm:
                return 'UK'
            elif '.edu' in realm:
                return 'USA'
            elif '.de' in realm:
                return 'Germany'
            elif '.fr' in realm:
                return 'France'
            elif '.nl' in realm:
                return 'Netherlands'
            elif '.se' in realm:
                return 'Sweden'
            else:
                return 'Unknown'
        
        df['home_country'] = df['realm'].apply(get_country_from_realm)
        
        # Determine visiting country/institution
        def get_visiting_location(from_inst, to_inst, ip):
            institutions = str(from_inst).lower() + ' ' + str(to_inst).lower()
            
            # Check if visiting Indian institutions
            if any(iit in institutions for iit in ['iit', 'iisc', 'iiser', 'nit']) or '14.139.' in str(ip) or '103.' in str(ip):
                return 'India'
            elif 'eduroam.org' in institutions:
                return 'International'
            else:
                return 'Unknown'
        
        df['visiting_country'] = df.apply(
            lambda row: get_visiting_location(row['from_inst'], row['to_inst'], row['ip']),
            axis=1
        )
        
        # Determine roaming status
        df['is_roaming'] = (df['home_country'] != df['visiting_country']) & (df['home_country'] != 'Unknown')
        
        # Get coordinates for mapping
        def get_coordinates(inst_name, country):
            inst_key = str(inst_name).lower().replace('_idp_sp', '').replace('_sp', '')
            if inst_key in self.institution_coordinates:
                return self.institution_coordinates[inst_key]
            elif country in self.country_coordinates:
                return self.country_coordinates[country]
            else:
                return [0, 0]
        
        df[['latitude', 'longitude']] = df.apply(
            lambda row: get_coordinates(row['to_inst'], row['visiting_country']),
            axis=1, result_type='expand'
        )
        
        # Add random variation to coordinates for better visualization
        df['latitude'] += np.random.uniform(-0.1, 0.1, len(df))
        df['longitude'] += np.random.uniform(-0.1, 0.1, len(df))
        
        # Connection success/failure
        df['connection_success'] = df['status'].apply(lambda x: 'Success' if x == 'Accept' else 'Failed')
        
        return df
    
    def analyze_movements(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze user movements and generate insights"""
        if df.empty:
            return {}
        
        analysis = {
            'total_users': len(df['user'].unique()),
            'indian_users': len(df[df['user_type'] == 'Indian']['user'].unique()),
            'foreign_users': len(df[df['user_type'] == 'Foreign']['user'].unique()),
            'total_connections': len(df),
            'successful_connections': len(df[df['status'] == 'Accept']),
            'failed_connections': len(df[df['status'] == 'Reject']),
            'roaming_sessions': len(df[df['is_roaming'] == True]),
            'countries_involved': len(df['home_country'].unique()),
        }
        
        # User movement patterns
        user_movements = {}
        for user in df['user'].unique():
            if user == 'unknown':
                continue
                
            user_data = df[df['user'] == user].sort_values('timestamp')
            user_movements[user] = {
                'user_type': user_data['user_type'].iloc[0],
                'home_country': user_data['home_country'].iloc[0],
                'movements': user_data.to_dict('records'),
                'institutions_visited': list(user_data['to_inst'].unique()),
                'countries_visited': list(user_data['visiting_country'].unique()),
                'total_connections': len(user_data),
                'successful_connections': len(user_data[user_data['status'] == 'Accept']),
                'is_roaming': any(user_data['is_roaming']),
                'roaming_sessions': len(user_data[user_data['is_roaming'] == True])
            }
        
        analysis['user_movements'] = user_movements
        
        # Institution analysis
        institution_stats = df.groupby('to_inst').agg({
            'user': 'nunique',
            'status': lambda x: (x == 'Accept').sum(),
            'is_roaming': 'sum'
        }).rename(columns={'user': 'unique_users', 'status': 'successful_connections', 'is_roaming': 'roaming_users'})
        
        analysis['institution_stats'] = institution_stats.to_dict('index')
        
        return analysis
    
    def create_movement_map(self, df: pd.DataFrame) -> folium.Map:
        """Create interactive movement map showing user connections across institutions"""
        if df.empty:
            return folium.Map(location=[20.5937, 78.9629], zoom_start=2)
        
        # Center map on India
        m = folium.Map(location=[20.5937, 78.9629], zoom_start=4)
        
        # Colors for different user types
        colors = {'Indian': 'green', 'Foreign': 'red'}
        
        # Add markers for each connection
        for _, row in df.iterrows():
            if row['latitude'] == 0 and row['longitude'] == 0:
                continue
                
            popup_text = f"""
            <div style="width: 200px;">
                <b>User:</b> {row['user'][:20]}...<br>
                <b>Type:</b> {row['user_type']}<br>
                <b>From:</b> {row['from_inst']}<br>
                <b>To:</b> {row['to_inst']}<br>
                <b>Status:</b> {row['status']}<br>
                <b>Time:</b> {row['timestamp']}<br>
                <b>Roaming:</b> {'Yes' if row['is_roaming'] else 'No'}<br>
                <b>Home Country:</b> {row['home_country']}<br>
                <b>Visiting:</b> {row['visiting_country']}
            </div>
            """
            
            # Icon based on connection status
            icon_color = colors.get(row['user_type'], 'blue')
            if row['status'] == 'Reject':
                icon_color = 'red'
            
            folium.Marker(
                [row['latitude'], row['longitude']],
                popup=folium.Popup(popup_text, max_width=250),
                icon=folium.Icon(
                    color=icon_color,
                    icon='user' if row['user_type'] == 'Foreign' else 'home'
                ),
                tooltip=f"{row['user']} - {row['to_inst']}"
            ).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 180px; height: 90px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p><b>Legend</b></p>
        <p><i class="fa fa-home" style="color:green"></i> Indian Users</p>
        <p><i class="fa fa-user" style="color:red"></i> Foreign Users</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m

def main():
    # Move both logos to the right corner and increase their size
    col_title, col_logo1, col_logo2 = st.columns([6, 1, 1])
    with col_title:
        st.markdown('<div style="height: 40px;"></div>', unsafe_allow_html=True)
    with col_logo1:
        st.image("/Users/bunny2ritik/Downloads/educom/images.png", width=220)  # Increased size
    with col_logo2:
        st.image("/Users/bunny2ritik/Downloads/educom/Ministry_of_Electronics_and_Information_Technology.png", width=220)  # Increased size

    st.markdown('<div class="main-header"><h1>🎓 Eduroam User Movement Analytics Dashboard</h1></div>', 
                unsafe_allow_html=True)
    
    # Initialize analyzer
    analyzer = EduroamLogAnalyzer()
    
    # Sidebar for file upload and controls
    with st.sidebar:
        st.header("📁 Panel 1 - Eduroam Log Reader")
        
        uploaded_file = st.file_uploader(
            "Upload Eduroam Log File",
            type=['txt', 'log'],
            help="Upload your eduroam authentication log file"
        )
        
        st.markdown("---")
        st.header("🔍 Filters & Controls")
        
        if uploaded_file is not None:
            # Process the file
            log_content = str(uploaded_file.read(), "utf-8")
            
            with st.spinner("Processing eduroam log file..."):
                df = analyzer.parse_eduroam_log(log_content)
            
            if not df.empty:
                # Store in session state
                st.session_state.df = df
                st.session_state.analysis = analyzer.analyze_movements(df)
                
                st.success(f"✅ Processed {len(df)} log entries")
                
                # Filters
                user_type_filter = st.multiselect(
                    "User Type",
                    options=['Indian', 'Foreign'],
                    default=['Indian', 'Foreign']
                )
                
                status_filter = st.multiselect(
                    "Connection Status",
                    options=['Accept', 'Reject'],
                    default=['Accept', 'Reject']
                )
                
                if len(df['home_country'].unique()) > 1:
                    country_filter = st.multiselect(
                        "Home Countries",
                        options=sorted(df['home_country'].unique()),
                        default=sorted(df['home_country'].unique())
                    )
                else:
                    country_filter = list(df['home_country'].unique())
                
                roaming_filter = st.selectbox(
                    "Roaming Status",
                    options=['All', 'Roaming Only', 'Non-Roaming Only']
                )
                
                date_range = st.date_input(
                    "Date Range",
                    value=[df['timestamp'].min().date(), df['timestamp'].max().date()],
                    min_value=df['timestamp'].min().date(),
                    max_value=df['timestamp'].max().date()
                )
    
    # Main content
    if 'df' in st.session_state:
        df = st.session_state.df
        analysis = st.session_state.analysis
        
        # Apply filters
        if 'user_type_filter' in locals():
            df_filtered = df[
                (df['user_type'].isin(user_type_filter)) &
                (df['status'].isin(status_filter)) &
                (df['home_country'].isin(country_filter)) &
                (df['timestamp'].dt.date >= date_range[0]) &
                (df['timestamp'].dt.date <= (date_range[1] if len(date_range) > 1 else date_range[0]))
            ]
            
            if roaming_filter == 'Roaming Only':
                df_filtered = df_filtered[df_filtered['is_roaming'] == True]
            elif roaming_filter == 'Non-Roaming Only':
                df_filtered = df_filtered[df_filtered['is_roaming'] == False]
        else:
            df_filtered = df
        
        # Key Metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            total_users = len(df_filtered['user'].unique())
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #2a5298; margin: 0;">👥 Total Users</h3>
                <h2 style="margin: 5px 0;">{total_users}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            indian_users = len(df_filtered[df_filtered['user_type'] == 'Indian']['user'].unique())
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #28a745; margin: 0;">🇮🇳 Indian Users</h3>
                <h2 style="margin: 5px 0;">{indian_users}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            foreign_users = len(df_filtered[df_filtered['user_type'] == 'Foreign']['user'].unique())
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #dc3545; margin: 0;">🌍 Foreign Users</h3>
                <h2 style="margin: 5px 0;">{foreign_users}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            roaming_users = len(df_filtered[df_filtered['is_roaming'] == True]['user'].unique())
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #ff6b6b; margin: 0;">📡 Roaming Users</h3>
                <h2 style="margin: 5px 0;">{roaming_users}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            success_rate = (len(df_filtered[df_filtered['status'] == 'Accept']) / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #17a2b8; margin: 0;">✅ Success Rate</h3>
                <h2 style="margin: 5px 0;">{success_rate:.1f}%</h2>
            </div>
            """, unsafe_allow_html=True)
        
        # Tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Analytics & Insights", "🗺️ Movement Map", "👤 User Details", "📈 Visualizations"])
        
        with tab1:
            st.header("📊 Analytics & Insights")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🇮🇳 Indian Users Analysis")
                indian_df = df_filtered[df_filtered['user_type'] == 'Indian']
                
                if not indian_df.empty:
                    st.write(f"**Total Indian Users:** {len(indian_df['user'].unique())}")
                    st.write(f"**Total Connections:** {len(indian_df)}")
                    st.write(f"**Successful Connections:** {len(indian_df[indian_df['status'] == 'Accept'])}")
                    st.write(f"**Roaming Sessions:** {len(indian_df[indian_df['is_roaming'] == True])}")
                    
                    # Top institutions for Indian users
                    top_institutions = indian_df['to_inst'].value_counts().head(5)
                    st.write("**Top Visited Institutions:**")
                    for inst, count in top_institutions.items():
                        st.write(f"• {inst}: {count} connections")
                        
                    # Countries visited by Indian users
                    countries_visited = indian_df['visiting_country'].value_counts()
                    st.write("**Countries/Regions Visited:**")
                    for country, count in countries_visited.items():
                        st.write(f"• {country}: {count} connections")
                else:
                    st.info("No Indian users in filtered data")
            
            with col2:
                st.subheader("🌍 Foreign Users Analysis")
                foreign_df = df_filtered[df_filtered['user_type'] == 'Foreign']
                
                if not foreign_df.empty:
                    st.write(f"**Total Foreign Users:** {len(foreign_df['user'].unique())}")
                    st.write(f"**Total Connections:** {len(foreign_df)}")
                    st.write(f"**Successful Connections:** {len(foreign_df[foreign_df['status'] == 'Accept'])}")
                    
                    # Foreign users' home countries
                    home_countries = foreign_df['home_country'].value_counts()
                    st.write("**Home Countries:**")
                    for country, count in home_countries.items():
                        st.write(f"• {country}: {count} connections")
                    
                    # Foreign users in India
                    foreign_in_india = foreign_df[foreign_df['visiting_country'] == 'India']
                    if not foreign_in_india.empty:
                        st.write(f"**Foreign Users in India:** {len(foreign_in_india['user'].unique())}")
                        
                        india_institutions = foreign_in_india['to_inst'].value_counts().head(5)
                        st.write("**Indian Institutions Visited:**")
                        for inst, count in india_institutions.items():
                            st.write(f"• {inst}: {count} connections")
                else:
                    st.info("No foreign users in filtered data")
            
            # Roaming Analysis
            st.subheader("📡 Roaming Analysis")
            col3, col4 = st.columns(2)
            
            with col3:
                roaming_df = df_filtered[df_filtered['is_roaming'] == True]
                if not roaming_df.empty:
                    st.write(f"**Total Roaming Sessions:** {len(roaming_df)}")
                    st.write(f"**Users with Roaming:** {len(roaming_df['user'].unique())}")
                    
                    # Most common roaming patterns
                    roaming_patterns = roaming_df.groupby(['home_country', 'visiting_country']).size().sort_values(ascending=False).head(5)
                    st.write("**Top Roaming Patterns:**")
                    for (home, visiting), count in roaming_patterns.items():
                        st.write(f"• {home} → {visiting}: {count} sessions")
                else:
                    st.info("No roaming sessions in filtered data")
            
            with col4:
                # Connection success rates
                if not df_filtered.empty:
                    success_by_type = df_filtered.groupby('user_type')['status'].apply(lambda x: (x == 'Accept').mean() * 100)
                    st.write("**Success Rates by User Type:**")
                    for user_type, rate in success_by_type.items():
                        st.write(f"• {user_type}: {rate:.1f}%")
                    
                    # Peak hours analysis
                    df_filtered['hour'] = df_filtered['timestamp'].dt.hour
                    peak_hours = df_filtered['hour'].value_counts().head(3)
                    st.write("**Peak Connection Hours:**")
                    for hour, count in peak_hours.items():
                        st.write(f"• {hour}:00 - {count} connections")
                else:
                    st.info("No data available for success rate analysis")
        
        with tab2:
            st.header("🗺️ Interactive Movement Map")
            st.write("Track user connections across eduroam institutions")
            
            # Create and display map
            movement_map = analyzer.create_movement_map(df_filtered)
            folium_static(movement_map, width=1200, height=600)
            
            # Map statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Locations on Map", len(df_filtered[df_filtered['latitude'] != 0]))
            with col2:
                st.metric("Countries Represented", len(df_filtered['visiting_country'].unique()))
            with col3:
                st.metric("Institutions Involved", len(df_filtered['to_inst'].unique()))
        
        with tab3:
            st.header("👤 Detailed User Movement History")
            
            # User selection
            available_users = [user for user in df_filtered['user'].unique() if user != 'unknown']
            if available_users:
                selected_user = st.selectbox(
                    "Select User",
                    options=available_users,
                    help="Choose a user to view their complete movement history"
                )
                
                if selected_user:
                    user_data = df_filtered[df_filtered['user'] == selected_user].sort_values('timestamp')
                    user_type = user_data['user_type'].iloc[0]
                    
                    # User info card
                    card_class = "foreign-user" if user_type == "Foreign" else "indian-user"
                    if any(user_data['is_roaming']):
                        card_class += " roaming-user"
                    
                    st.markdown(f"""
                    <div class="user-card {card_class}">
                        <h3>User: {selected_user}</h3>
                        <p><strong>Type:</strong> {user_type}</p>
                        <p><strong>Home Country:</strong> {user_data['home_country'].iloc[0]}</p>
                        <p><strong>Total Connections:</strong> {len(user_data)}</p>
                        <p><strong>Successful Connections:</strong> {len(user_data[user_data['status'] == 'Accept'])}</p>
                        <p><strong>Institutions Visited:</strong> {', '.join(user_data['to_inst'].unique())}</p>
                        <p><strong>Roaming Sessions:</strong> {len(user_data[user_data['is_roaming'] == True])}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Movement timeline
                    st.subheader("📅 Connection Timeline")
                    
                    for i, (_, row) in enumerate(user_data.iterrows()):
                        status_class = "success-connection" if row['status'] == 'Accept' else "failed-connection"
                        roaming_indicator = "🌍 ROAMING" if row['is_roaming'] else "🏠 HOME"
                        
                        st.markdown(f"""
                        <div class="{status_class}">
                            <h4>Connection {i+1} - {row['status']} {roaming_indicator}</h4>
                            <p><strong>Timestamp:</strong> {row['timestamp']}</p>
                            <p><strong>From Institution:</strong> {row['from_inst']}</p>
                            <p><strong>To Institution:</strong> {row['to_inst']}</p>
                            <p><strong>Station ID:</strong> {row.get('stationid', 'N/A')}</p>
                            <p><strong>IP Address:</strong> {row['ip']}</p>
                            <p><strong>Visiting Country:</strong> {row['visiting_country']}</p>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No users available in filtered data")
        
        with tab4:
            st.header("📈 Data Visualizations")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # User type distribution
                if not df_filtered.empty:
                    user_type_counts = df_filtered.groupby('user_type')['user'].nunique()
                    if len(user_type_counts) > 0:
                        fig1 = px.pie(
                            values=user_type_counts.values,
                            names=user_type_counts.index,
                            title="User Type Distribution",
                            color_discrete_map={'Indian': '#28a745', 'Foreign': '#dc3545'}
                        )
                        fig1.update_layout(height=400)
                        st.plotly_chart(fig1, width='stretch')
                    else:
                        st.info("No user type data available")
                
                # Connection status distribution
                if not df_filtered.empty:
                    status_counts = df_filtered['status'].value_counts()
                    if len(status_counts) > 0:
                        fig3 = px.bar(
                            x=status_counts.index,
                            y=status_counts.values,
                            title="Connection Status Distribution",
                            color=status_counts.values,
                            color_continuous_scale='RdYlGn'
                        )
                        fig3.update_layout(height=400)
                        st.plotly_chart(fig3, width='stretch')
                    else:
                        st.info("No status data available")
            
            with col2:
                # Connections over time
                if not df_filtered.empty:
                    df_filtered['date'] = df_filtered['timestamp'].dt.date
                    daily_connections = df_filtered.groupby(['date', 'status']).size().reset_index(name='connections')
                    
                    if len(daily_connections) > 0:
                        fig2 = px.line(
                            daily_connections,
                            x='date',
                            y='connections',
                            color='status',
                            title="Daily Connection Trends",
                            color_discrete_map={'Accept': '#28a745', 'Reject': '#dc3545'}
                        )
                        fig2.update_layout(height=400)
                        st.plotly_chart(fig2, width='stretch')
                    else:
                        st.info("No daily connection data available")
                
                # Top institutions
                if not df_filtered.empty and 'to_inst' in df_filtered.columns:
                    top_institutions = df_filtered['to_inst'].value_counts().head(10)
                    if len(top_institutions) > 0:
                        fig4 = px.bar(
                            x=top_institutions.values,
                            y=top_institutions.index,
                            title="Top Visited Institutions",
                            orientation='h'
                        )
                        fig4.update_layout(height=400)
                        st.plotly_chart(fig4, width='stretch')
                    else:
                        st.info("No institution data available")
            
            # Additional visualizations
            st.subheader("📊 Advanced Analytics")
            
            col3, col4 = st.columns(2)
            
            with col3:
                # Hourly connection pattern
                if not df_filtered.empty:
                    hourly_pattern = df_filtered.groupby(df_filtered['timestamp'].dt.hour).size()
                    if len(hourly_pattern) > 0:
                        fig5 = px.bar(
                            x=hourly_pattern.index,
                            y=hourly_pattern.values,
                            title="Hourly Connection Pattern",
                            labels={'x': 'Hour of Day', 'y': 'Number of Connections'}
                        )
                        fig5.update_layout(height=400)
                        st.plotly_chart(fig5, width='stretch')
                    else:
                        st.info("No hourly data available")
            
            with col4:
                # Roaming vs Non-roaming - FIXED VERSION
                if not df_filtered.empty and 'is_roaming' in df_filtered.columns:
                    roaming_counts = df_filtered['is_roaming'].value_counts()
                    
                    # Ensure both True and False are represented
                    roaming_counts = roaming_counts.reindex([False, True], fill_value=0)
                    
                    if roaming_counts.sum() > 0:
                        fig6 = px.pie(
                            values=roaming_counts.values,
                            names=['Non-Roaming', 'Roaming'],
                            title="Roaming vs Non-Roaming Connections",
                            color_discrete_sequence=['#17a2b8', '#ffc107']
                        )
                        fig6.update_layout(height=400)
                        st.plotly_chart(fig6, width='stretch')
                    else:
                        st.info("No roaming data available")
                else:
                    st.info("No roaming data available for analysis")
            
            # Heat map of user activity
            if len(df_filtered) > 0:
                st.subheader("🔥 User Activity Heatmap")
                df_filtered['day_of_week'] = df_filtered['timestamp'].dt.day_name()
                df_filtered['hour'] = df_filtered['timestamp'].dt.hour
                
                heatmap_data = df_filtered.groupby(['day_of_week', 'hour']).size().reset_index(name='connections')
                
                if len(heatmap_data) > 0:
                    heatmap_pivot = heatmap_data.pivot(index='day_of_week', columns='hour', values='connections').fillna(0)
                    
                    # Reorder days
                    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    heatmap_pivot = heatmap_pivot.reindex([day for day in day_order if day in heatmap_pivot.index])
                    
                    if not heatmap_pivot.empty:
                        fig7 = px.imshow(
                            heatmap_pivot.values,
                            x=heatmap_pivot.columns,
                            y=heatmap_pivot.index,
                            title="User Activity Heatmap (Day vs Hour)",
                            color_continuous_scale='Blues',
                            labels={'x': 'Hour of Day', 'y': 'Day of Week', 'color': 'Connections'}
                        )
                        fig7.update_layout(height=500)
                        st.plotly_chart(fig7, width='stretch')
                    else:
                        st.info("No heatmap data available")
                else:
                    st.info("No data available for activity heatmap")
        
        # Raw data view
        with st.expander("📋 View Raw Log Data"):
            st.dataframe(df_filtered, height=400)
            
            # Download processed data
            csv = df_filtered.to_csv(index=False)
            st.download_button(
                label="📥 Download Processed Data",
                data=csv,
                file_name=f"eduroam_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    else:
        # Welcome screen
        st.markdown("""
        <div style="text-align: center; padding: 50px;">
            <h2>Welcome to Eduroam User Movement Analytics</h2>
            <p style="font-size: 18px; color: #666;">
                Upload your eduroam authentication log file to start analyzing user movement patterns, 
                roaming behavior, and institutional connections across the eduroam network.
            </p>
            <div style="margin: 30px 0;">
                <h3>📋 Features:</h3>
                <ul style="text-align: left; display: inline-block;">
                    <li>📁 Parse eduroam authentication logs</li>
                    <li>🔍 Separate analysis for Indian vs Foreign users</li>
                    <li>🗺️ Interactive maps showing institutional connections</li>
                    <li>📊 Comprehensive analytics and success rate tracking</li>
                    <li>👤 Detailed user connection history</li>
                    <li>📱 Roaming analysis and institutional mobility</li>
                    <li>🎯 Foreign user tracking in Indian institutions</li>
                </ul>
            </div>
            <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h4>📝 Supported Log Format:</h4>
                <p style="text-align: left; font-family: monospace; font-size: 12px;">
                    Thu Jul 25 09:03:00 2024: Access-Accept for user user@domain.edu stationid ABC123 from inst1_SP to inst2_SP (IP)<br>
                    Thu Jul 25 09:03:00 2024: F-TICKS/eduroam/1.0#REALM=domain.edu#VISCOUNTRY=IN#VISINST=inst_SP#CSI=...#RESULT=OK#
                </p>
            </div>
            <p style="color: #999;">Use the sidebar to upload your eduroam log file and get started!</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
