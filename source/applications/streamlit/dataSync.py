# common imports
from datetime import datetime, timedelta

# front-end imports
import streamlit as st

# ===========================================
# Functions Data Retrieval
# ===========================================
@st.cache(allow_output_mutation=True, suppress_st_warning=True)
def getBestLags(df, tags, target, shiftFrom, shiftTo, shiftStep):
    return resultPearson, resultMic, resultSpearman, resultKendall

##########################
### App page beginning ###
##########################


def write(state):

    if type(state.dfRawRange) == type(None):
        st.warning(
            "Realize a importação do arquivo CSV contendo os dados em **'Data Preparation'**."
        )

    elif state.dfRawRange.empty:

        st.warning("Realize os passos 1 e 2 do **'Data Preparation'**.")

    else:

        # st.markdown("Pronto! Dados carregados com sucesso!")
        st.sidebar.title("Data Syncronization")

        # ===========================================
        # Body
        # ===========================================

        st.title("Obtendo os datasets sincronizados")
        st.markdown(
            "A última etapa para finalmente obter os dados **sincronizados** é utilizar o cálculo de correlação para encontrar a correta **defasagem (lag)** entre a variável de processo e de qualidade."
        )
        st.subheader("")
