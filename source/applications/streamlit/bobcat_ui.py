import streamlit as st

import defSessionState as ss

import home
import dataPreparation
import dataUnderstanding
import dataSync

PAGES = {
    "Home": home,
    "Run Bobcat": dataPreparation,
    "View Results": dataUnderstanding,
}

st.set_page_config(
    # Can be "centered" or "wide". In the future also "dashboard", etc.
    layout="wide",
    initial_sidebar_state="expanded",  # Can be "auto", "expanded", "collapsed"
    # String or None. Strings get appended with "• Streamlit".
    page_title="Bobcat",
    page_icon=None,  # String, anything supported by st.image, or None.
)

def main():
    state = ss._get_state()

    # result, username, check = lg.login(c, conn)

    # if result and check:

    #    st.sidebar.success("Logged In as {}".format(username))
    st.sidebar.title("Navigation")
    selection = st.sidebar.radio("Go to", list(PAGES.keys()))

    page = PAGES[selection].write(state)

    st.sidebar.title("About")
    st.sidebar.info(
        """
        This app is utilizing Bobcat v1.0.4
        """
    )

    # elif not result and check:
    #    st.sidebar.warning("Incorrect Username/Password")

    state.sync()


if __name__ == "__main__":
    main()
