import streamlit as st
import asyncio,os,json

# Import your invoke function
from content_generation.app import invoke  # Replace 'your_module' with the actual module name
#from content_generation import app  # Replace 'your_module' with the actual module name


# Helper function to handle async calls
async def handle_invoke(event):
    return await invoke(event)

# Streamlit app
st.title("SEO Expert Suite by VVTS")
st.markdown("A sophisticated AI tool that combines SEO expertise with professional content creation. From competitor analysis to final content, it handles every step of creating search-optimized, authoritative content.")
# Input box for user to type the event
user_input = st.text_input("Enter your keyword:", "")

# Button to trigger the invoke function
if st.button("Submit"):
    if user_input:
        try:
            # Call the async invoke function
            response = asyncio.run(handle_invoke(user_input))
            
            # Assuming response is a JSON object
            if isinstance(response, str):
                response = json.loads(response)  # Parse if it's a JSON string

            st.success("Response Received!")

            # Display SEO Blog Data
            st.subheader("Expert Copy:")
            seo_blog_data = response.get("seo_blog_data", "")
            #print(seo_blog_data)
            if seo_blog_data:
                st.html(seo_blog_data)
            else:
                st.write("No SEO blog data available.")

            # Display QC Data
            st.subheader("QC Data:")
            qc_data = response.get("qc_data", "")
            #print(seo_blog_data)
            if qc_data:
                st.markdown(qc_data)
            else:
                st.write("No QC Data available.")


            # Display SEO Blog blue print Data
            st.subheader("Blog blue print Data:")
            seo_expert_data = response.get("seo_expert_data", "")
            #print(seo_blog_data)
            if seo_expert_data:
                st.html(seo_expert_data)
            else:
                st.write("No SEO Expert data available.")

            # Display Tokens Consumption Data
            st.subheader("Total Tokens Consumption:")
            tokens = response.get("combined_tokens", "")
            #print(seo_blog_data)
            if tokens:
                st.html(tokens)
            else:
                st.write("Tokens data available.")

            # Display URLs
            st.subheader("Exracted URLs:")
            urls = response.get("urls", [])
            if urls:
                for url in urls:
                    st.markdown(f"- [{url}]({url})")
            else:
                st.write("No URLs available.")

            

            # Display Web Scraped Data
            st.subheader("Web Scraped Data")
            web_scrap_data = response.get("web_scrap_data", [])
            if web_scrap_data:
                for idx, item in enumerate(web_scrap_data, start=1):
                    st.markdown(
                        f"""
                        <div style="display: flex; align-items: flex-start;">
                            <span style="font-size:35px; font-weight:bold; margin-right:8px;">{idx}.</span>
                            <span style="font-size:20x;">{item}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.write("No web scraped data available.")


            # Display Research Data
            st.subheader("Research Data:")
            research_data = response.get("research_data", [])
            if research_data:
                for idx, data in enumerate(research_data, start=1):
                    st.markdown(
                        f"""
                        <div style="display: flex; align-items: flex-start;">
                            <span style="font-size:35px; font-weight:bold; margin-right:8px;">{idx}.</span>
                            <span style="font-size:20x;">{data}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.write("No research data available.")

            # Display Websearch  Data
            st.subheader("Websearch Data:")
            websearch_data = response.get("websearch_data", "")
            if websearch_data:
                for idx, x in enumerate(websearch_data, start=1):
                    st.markdown( 
                        f"""
                        <div style="display: flex; align-items: flex-start;">
                            <span style="font-size:35px; font-weight:bold; margin-right:8px;">{idx}.</span>
                            <span style="font-size:20x;">{x}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.write("No Websearch data available.")
        except Exception as e:
            st.error(f"An error occurred: {e}")

            
    else:
        st.warning("Please enter an event.")

st.markdown("Disclaimer: Currently in prototype stage. Features and functionality may evolve during development.")
    