# front-end imports
import streamlit as st
import pandas as pd
import base64
from pathlib import Path
import shutil
import os

import streamlit.components.v1 as components

@st.cache(allow_output_mutation=True)
def getDataFromCSV(file) -> pd.DataFrame:
    dataFrame = pd.read_csv(file, sep=",", decimal=".",
                     encoding="UTF-8", 
                     index_col=3,
                     low_memory=False)
    
    dataFrame.index = pd.to_datetime(dataFrame.index, format='%Y-%m-%d %H:%M:%S')
    dataFrame = dataFrame.sort_index(ascending=True)
    #dataFrame = dataFrame.apply(pd.to_numeric, errors='coerce')
    return dataFrame

def write(state):
    
    st.title("View Data Results")
    st.markdown("------------------------------------------")
    for _, results, _ in os.walk('Results'):
        break
    results.sort(key=lambda x: os.path.getmtime('Results/'+x), reverse=True)
    
    if len(results) == 0:
        st.warning("There's no data to be found.")
    else:
        run = st.radio('Pick a run result:', options=results[:10])
        st.warning('Limited to showing only the most recent 10 runs on the machine. If you need to go further back, please download these results and delete them.')
        st.markdown("------------------------------------------")
        if st.checkbox('Show limited message history'):
            df = getDataFromCSV('Results/'+run+'/msg_history.csv')
            st.dataframe(df.drop(columns='data').head(20))
        
        
        if ['czml'] in [x for x in os.walk('Results/'+run)][0]:
            if st.checkbox('Show CZML files'):
                showCZML = []
                st.subheader('Select files to visualize.')
                for root, nodes, files in os.walk('Results/'+run+'/czml'):
                    for file in files:
                        showCZML.append([root+"/"+file, st.checkbox(root[root.find('czml')+5:]+"/"+file)])
                
                #Cesium Component
                add = ""
                for czml in showCZML:
                    if czml[1]:
                        with open(czml[0], 'r') as f:
                            add += "var dataSource = "
                            add += f.read()
                            add += ";var dataSourcePromise = Cesium.CzmlDataSource.load(dataSource);viewer.dataSources.add(dataSourcePromise);"
                        f.close()
                
                components.html(f"""
                    <script src="https://cesium.com/downloads/cesiumjs/releases/1.80/Build/Cesium/Cesium.js"></script>
                    <link href="https://cesium.com/downloads/cesiumjs/releases/1.80/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
                    <div id="cesiumContainer" style="height:550px;"></div>
                    <script>
                        var viewer = new Cesium.Viewer('cesiumContainer', {{
                            vrButton: false,
                            fullscreenButton: true,
                            timeline: true,
                            infoBox: false, 
                            fullscreenElement : cesiumContainer,
                            
                            imageryProvider : new Cesium.TileMapServiceImageryProvider({{
                              url : Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII')
                            }}),
                            baseLayerPicker : false,
                            homeButton : false,
                            geocoder : false,
                            navigationHelpButton : false,
                            }});
                        viewer.cesiumWidget.creditContainer.hidden=true;
                        """+add+"""
                        </script>
                        </div>
                    """, height=600)
                        
        
        if st.checkbox("Delete this result"):
            st.text("Are you sure? You would like to delete the following folder?")
            dir_path = Path.cwd().joinpath('Results',run)
            st.text(dir_path)
            if st.checkbox('Yes'):
                
                shutil.rmtree(dir_path)
                #st.text(dir_path.joinpath('Results',run))
                state.sync()
        
        
