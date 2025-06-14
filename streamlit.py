import streamlit as st
import os
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import PyPDF2
from io import BytesIO
from dotenv import load_dotenv

# Import your custom agents
from utils.Agents import Cardiologist, Psychologist, Pulmonologist, MultidisciplinaryTeam

# Page configuration
st.set_page_config(
    page_title="Medical Report Analysis",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .stProgress .st-bo {
        background-color: #667eea;
    }
    .upload-section {
        border: 2px dashed #667eea;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
    }
    .result-section {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def load_api_key():
    """Load API key from environment or user input"""
    # Try to load from .env file first
    load_dotenv(dotenv_path='apikey.env')
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        # If not found in env file, ask user to input
        st.sidebar.header("🔑 API Configuration")
        api_key = st.sidebar.text_input(
            "Enter your Google API Key:", 
            type="password",
            help="Get your API key from Google AI Studio: https://ai.google.dev"
        )
        
        if api_key:
            # Save to session state
            st.session_state['api_key'] = api_key
        else:
            st.sidebar.warning("Please enter your Google API Key to proceed.")
            return None
    else:
        st.session_state['api_key'] = api_key
    
    return api_key

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_file.read()))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        st.error(f"Error reading PDF file: {str(e)}")
        return None

def process_medical_report(medical_report, api_key):
    """Process the medical report using the AI agents"""
    
    # Initialize progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Initialize agents
        status_text.text("Initializing AI agents...")
        progress_bar.progress(10)
        
        agents = {
            "Cardiologist": Cardiologist(medical_report, api_key=api_key),
            "Psychologist": Psychologist(medical_report, api_key=api_key),
            "Pulmonologist": Pulmonologist(medical_report, api_key=api_key)
        }
        
        progress_bar.progress(20)
        
        # Function to run each agent and get their response
        def get_response(agent_name, agent):
            response = agent.run()
            if response is None:
                st.warning(f"Warning: {agent_name} failed to generate a response, likely due to API issues.")
            return agent_name, response
        
        # Run the agents concurrently and collect responses
        status_text.text("Running specialist consultations...")
        responses = {}
        
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(get_response, name, agent): name for name, agent in agents.items()}
            
            completed = 0
            for future in as_completed(futures):
                agent_name, response = future.result()
                responses[agent_name] = response
                completed += 1
                progress_bar.progress(20 + (completed * 20))
                status_text.text(f"Completed {agent_name} analysis...")
        
        # Check if any agent responses are None
        if None in responses.values():
            st.error("Error: One or more agents failed to generate a response. Check API key and quota.")
            return None, None
        
        progress_bar.progress(80)
        status_text.text("Generating multidisciplinary team analysis...")
        
        # Run the MultidisciplinaryTeam agent to generate the final diagnosis
        team_agent = MultidisciplinaryTeam(
            cardiologist_report=responses["Cardiologist"],
            psychologist_report=responses["Psychologist"],
            pulmonologist_report=responses["Pulmonologist"],
            api_key=api_key
        )
        
        final_diagnosis = team_agent.run()
        
        if final_diagnosis is None:
            st.error("Error: MultidisciplinaryTeam failed to generate a final diagnosis.")
            return None, None
        
        progress_bar.progress(100)
        status_text.text("Analysis completed successfully!")
        
        return responses, final_diagnosis
        
    except Exception as e:
        st.error(f"An error occurred during processing: {str(e)}")
        return None, None

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🏥 AI Medical Report Analysis</h1>
        <p>Advanced Multi-Specialist Medical Report Analysis System</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Load API key
    api_key = load_api_key()
    
    if not api_key:
        st.info("👈 Please configure your Google API Key in the sidebar to get started.")
        return
    
    # Sidebar information
    st.sidebar.header("ℹ️ About")
    st.sidebar.info("""
    This application analyzes medical reports using AI specialists:
    - **Cardiologist**: Heart-related assessments
    - **Psychologist**: Mental health evaluations  
    - **Pulmonologist**: Respiratory system analysis
    - **Multidisciplinary Team**: Comprehensive diagnosis
    """)
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📄 Upload Medical Report")
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Choose a medical report file",
            type=['txt', 'pdf'],
            help="Upload a medical report in PDF or TXT format"
        )
        
        medical_report_text = None
        
        if uploaded_file is not None:
            # Display file details
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            st.info(f"File size: {uploaded_file.size} bytes")
            
            # Process the uploaded file
            if uploaded_file.type == "text/plain":
                # Handle TXT file
                medical_report_text = str(uploaded_file.read(), "utf-8")
            elif uploaded_file.type == "application/pdf":
                # Handle PDF file
                medical_report_text = extract_text_from_pdf(uploaded_file)
            
            if medical_report_text:
                # Show preview of the text
                with st.expander("📖 Preview Medical Report"):
                    st.text_area("Report Content:", medical_report_text, height=200, disabled=True)
                
                # Analysis button
                if st.button("🔍 Start Analysis", type="primary", use_container_width=True):
                    st.session_state['analysis_started'] = True
                    st.session_state['medical_report'] = medical_report_text
    
    with col2:
        st.header("📊 Analysis Results")
        
        if 'analysis_started' in st.session_state and st.session_state['analysis_started']:
            # Process the medical report
            responses, final_diagnosis = process_medical_report(
                st.session_state['medical_report'], 
                api_key
            )
            
            if responses and final_diagnosis:
                # Display individual specialist reports
                st.subheader("👨‍⚕️ Specialist Reports")
                
                # Cardiologist Report
                with st.expander("🫀 Cardiologist Analysis"):
                    st.write(responses.get("Cardiologist", "No response"))
                
                # Psychologist Report
                with st.expander("🧠 Psychologist Analysis"):
                    st.write(responses.get("Psychologist", "No response"))
                
                # Pulmonologist Report
                with st.expander("🫁 Pulmonologist Analysis"):
                    st.write(responses.get("Pulmonologist", "No response"))
                
                # Final Diagnosis
                st.subheader("🏆 Final Multidisciplinary Analysis")
                st.markdown(f"""
                <div class="result-section">
                    {final_diagnosis}
                </div>
                """, unsafe_allow_html=True)
                
                # Prepare downloadable content
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                download_content = f"""
MEDICAL REPORT ANALYSIS
Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{'='*50}

CARDIOLOGIST ANALYSIS:
{responses.get("Cardiologist", "No response")}

{'='*50}

PSYCHOLOGIST ANALYSIS:
{responses.get("Psychologist", "No response")}

{'='*50}

PULMONOLOGIST ANALYSIS:
{responses.get("Pulmonologist", "No response")}

{'='*50}

FINAL MULTIDISCIPLINARY TEAM ANALYSIS:
{final_diagnosis}

{'='*50}
End of Report
                """
                
                # Download button
                st.download_button(
                    label="📥 Download Analysis Report",
                    data=download_content,
                    file_name=f"medical_analysis_{timestamp}.txt",
                    mime="text/plain",
                    type="primary",
                    use_container_width=True
                )
                
                # Reset session state
                if st.button("🔄 Analyze Another Report", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        if key.startswith('analysis') or key == 'medical_report':
                            del st.session_state[key]
                    st.rerun()
        else:
            st.info("👆 Upload a medical report and click 'Start Analysis' to begin.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🏥 AI Medical Report Analysis System | Powered by Google Gemini AI</p>
        <p><small>⚠️ This tool is for educational purposes only. Always consult with qualified healthcare professionals for medical advice.</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()