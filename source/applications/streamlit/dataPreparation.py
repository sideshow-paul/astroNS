# native imports
import datetime
import pandas

# front-end imports
import streamlit as st

import sys
sys.path.append('./source/bobcat')
from bobcat import main as bobcat
from multiprocessing import Process


@st.cache(allow_output_mutation=True)
def getDataFromYML(files):
    file_names = [file.name for file in files]
    file_values = [file.getvalue().decode() for file in files]
    for key, value in enumerate(file_names):
        with open("source/applications/streamlit/data"+value, "w") as f:
            f.write(file_values[key])
    return True


##########################
### App page beginning ###
##########################
def write_data(state, filenames):
    st.title("Next, select options from the left side.")

    st.sidebar.title("Simulation Options")

    expanderFltDate = st.sidebar.beta_expander(
        label="Step 1: Select the epoch", expanded=False
    )

    dt1 = expanderFltDate.date_input(label="Epoch Date:", value=state.fltDateStart)
    dt2 = expanderFltDate.text_input(label="Epoch Time", value="00:00:00")
    expanderFltDate.warning('All times assume Zulu')
    
    expanderFltTags = st.sidebar.beta_expander(
        label="Step 2: Select the primary network file", expanded=False
    )

    if len(filenames)>0:
        state.dfTags = [file.name for file in filenames]
    else:
        state.dfTags = ['propagator_viz.yml', 'spacecraft.yml']

    state.fltTags = expanderFltTags.selectbox(
        label="Select the primary file:",
        options=state.dfTags,
        key="fltTagsPreparation",
    )

    if state.fltTags != []:

        st.markdown("------------------------------------------")
        st.markdown(
            "If you want to take a double check the data, you may do so."
        )

        #################
        ### Dataframe ###
        #################

        showRawData = st.checkbox(
            label="View the input data", value=False, key="showRawData"
        )

        if showRawData:
            if len(filenames)>0:
                file_values = [file.getvalue().decode() for file in filenames]
            else:
                file_values = []
                with open('source/applications/streamlit/data/spacecraft.yml', 'r') as f:
                    file_values.append(f.read())
                with open('source/applications/streamlit/data/propagator_viz.yml', 'r') as f:
                    file_values.append(f.read())
                    
            st.text(
                "\n\n----------------NEXT UPLOADED FILE-------------------------\n\n".join(
                    file_values
                )
            )

        expanderFltRun = st.sidebar.beta_expander(
            label="Step 3: Run Bobcat", expanded=False
        )
        if expanderFltRun.button("Run Bobcat"):
            with st.spinner(text='In progress'):
                p1 = Process(target=bobcat, args=('source/applications/streamlit/data/'+state.fltTags,))
                p1.start()
                p1.join()
                st.success('Done')

def write(state):

    st.title("First, upload your Bobcat files.")
    st.markdown("Let's see what you want to run...")

    st.info(
        """
        This UI accepts files in YML format:
            \n* Multiple files can be connected together, but relative paths must be used.
        """
    )

    uploaded_file = st.file_uploader(
        "", type="yml", key="uploaded_file", accept_multiple_files=True
    )
    test = st.checkbox("Use test data")
    
    if uploaded_file:
        # Validation required
        data_load_state = st.text("Validating the file...")
        valid = getDataFromYML(uploaded_file)
        data_load_state.text("")
        write_data(state, uploaded_file)
    
    # Test data
    if test:
        write_data(state, uploaded_file)
        
    