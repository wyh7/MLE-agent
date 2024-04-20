from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from snowflake.snowpark import Session
from langchain.chains import create_sql_query_chain
from langchain.prompts import PromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import chain
from langchain_core.output_parsers import StrOutputParser

import json


# Load the configuration from a JSON file
def load_config(file_path):
    with open(file_path, 'r') as file:
        config = json.load(file)
    return config


def snowflake_config(config):
    snowflake_config = config["snowflake"]
    print(snowflake_config)
    # Create the Snowflake URL

    session = Session.builder.configs(snowflake_config).create()

    return session


def data_engineering_data_loading():
    # 1. Welcome the user to the MLE-agent
    print("Welcome to the MLE-agent!")

    # 2. Inform them about the current stage
    print("You are currently in the Data Engineering stage.")

    # 3. Ask the user to choose a data store
    print("Please choose a data store by entering the corresponding number:")
    print("1. Snowflake")
    print("2. Databricks")
    print("3. AWS S3")

    # 4. Process user input
    choice = input("Enter your choice (1, 2, or 3): ")

    # 5. Respond according to the user's choice
    data_stores = {
        '1': 'Snowflake',
        '2': 'Databricks',
        '3': 'AWS S3'
    }

    # Validate the user input
    if choice in data_stores:
        print(f"MLE-agent will now help you to load data from {data_stores[choice]}.")
    else:
        print("Invalid choice. Please run the program again and select 1, 2, or 3.")


@chain
def sql_agent(input: str, llm: BaseChatModel):
    """
    Analyze the user's current ML development stage based on their input description.

    Args:
        input (str): The user's input describing their current work.
        llm (BaseChatModel): The language model used for processing the input.

    Returns:
        MLDevelopmentStage: Enum representing the identified ML development stage.
    """
    output_parser = StrOutputParser()
    prompt = PromptTemplate(
        template="""
        You play as a professional data scientist. You are currently in the Data Engineering stage. You will understand 
        users input and generate SQL queries to Snowflake.  Do not add ; at the end of the query.

        The user's input description is: {input}
        The SQL query generated is:
        """,
        input_variables=["input"]
    )

    chain = prompt | llm | output_parser
    return chain.invoke({"input": input})


if __name__ == "__main__":
    # Assuming your configuration file is named 'config.json'

    data_engineering_data_loading()

    config = load_config('../credential.json')

    # Extract Snowflake and OpenAI configuration details
    OPENAI_API_KEY = config["OPENAI_API_KEY"]

    session = snowflake_config(config)

    llm = ChatOpenAI(api_key=OPENAI_API_KEY)

    prompt = "Show me top 5 records from IMDB_TEST"

    sql_query = sql_agent.invoke(
        input=prompt,
        llm=llm  # Assuming 'llm' is your instantiated language model
    )

    # we can visualize what sql query is generated by the LLM
    print(sql_query)

    session.sql(sql_query).show()
