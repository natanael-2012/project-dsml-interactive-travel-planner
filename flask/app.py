from dotenv import load_dotenv
import os
from flask import Flask, render_template, request
import openai
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import datetime
from chatbot_funcs import get_weather
from flask import session
import pickle

app = Flask(__name__)
######################
# openai.api_key  = "<place your openai_api_key>"
load_dotenv('../.env')

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
from openai import OpenAI
client = OpenAI(
    api_key=OPENAI_API_KEY
)

# Initialize the SentenceTransformer embeddings
with open ('sentence_transformer_embeddings.pkl', 'rb') as f:
    sentence_transformer_embeddings = pickle.load(f)
# print("Initialized SentenceTransformer embeddings.")

# print("\nLoading database...")
db = Chroma(persist_directory='../chroma_db', embedding_function=sentence_transformer_embeddings)
rag_response = None

#
import json
def gpt_extract_info(user_input, current_step, conversation_state):
    """
    Extract multiple pieces of information from the user's input.
    For example, dates, interests, locations, and questions.
    """
    if current_step == "start":
        prompt = f"""
        Analyze the user input and extract relevant information such as travel dates, interests and location information.

        For example, if the user input is "I want to go to Cabo Rojo on February 15 to go to the beach"
        The model should return the structured information in a JSON format:
        {{  "travel_dates": ["2025-02-15"],
            "interests": "beaches, Cabo Rojo" }}

        The date should be in YYYY-MM-DD for it to be valid.
            
        If the user input is "Hello" just return
        {{  "travel_dates": null,
            "interests": null }}

        If they input "Hello. Where can i hike?", return 
        {{  "travel_dates": null,
            "interests": "hiking" }}
        Today's date {str(datetime.date.today())}
        User input: {user_input}
        """
    elif current_step == "received_interests":
        prompt = f"""Analyze the user input and extract their interests. 
        For example, if the user input is "I like hiking and beaches", the model should return the structured information in a JSON format: {{"interests": "hiking, beaches"}}. 
        If the user input is "Hello. Where can I hike?", the model should return {{"interests": "hiking"}}. 
        User input: {user_input}"""

    elif current_step == "received_location":
        prompt = f"""Analyze the user input and decide if the user mentioned a location they want to go to.
        For example, if the user input is "I want to go to Cabo Rojo", the model should return the structured information in a JSON format: {{"current_location": "Cabo Rojo"}}.
        If they answer "yes", they may be responding to the previous question. Here is the context of {conversation_state['messages'][-2:]} Add the place to the current location.
        User input: {user_input}"""

    elif current_step == "ask_accept_location":
        prompt = f"""Analyze the user input and decide if the user accepted or declined the suggested location.
        If they accept, return a JSON like this {{'user_decision': 'accept'}}. If they decline, return a JSON like this {{'user_decision': 'decline'}}.
        User input: {user_input}"""


    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            'role': 'user', 
            'content':prompt
            }],
        response_format={
            "type": "json_object"
            },
        max_tokens=200,
        temperature=0.5
    )
    # print(gpt_response)
    gpt_response=json.loads(response.choices[0].message.content)
    
    print("inside gpt_extract_info")
    
    return gpt_response



#
def is_weather_dependent(location):
    """
    Ask GPT whether a location is weather dependent or not.
    """
    prompt = f"""Is the location '{location}' highly dependent on weather conditions? (e.g., outdoor activities, beach, hiking). 
    For example, if the location is El Morrow, the model should return True. If its a museum, the model should return False.
    Return a JSON object with the key 'weather_dependent' and the boolean values of True (for highly dependant) or False (for not highly dependant).
    
    Once again: is the location '{location}' highly dependent on weather conditions?"""

    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            'role': 'user', 
            'content':prompt
            }],
        response_format={
            "type": "json_object"
            },
        max_tokens=200,
        temperature=0.5
    )
    
    gpt_response=json.loads(response.choices[0].message.content)
    print("inside is_weather_dependent")
    return gpt_response['weather_dependent']


#
def check_weather(location, travel_dates):
    """
    Ask GPT or an API to check the weather for the given location and travel dates.
    """
    weather = get_weather(str(location), str(travel_dates[0]))
    print(weather)
    prompt = f"""You will tell me if the weather will be bad for outside activities. Respond in JSON format, with key "bad_weather" and boolean value.
        The temperature will be of {weather['temp']['value']} deg Farenheit. The humidity level is of {weather["humidity"]['value']}%. 
        A brief description of the weather is: {weather['weather']}."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            'role': 'user', 
            'content':prompt
            }],
        response_format={
            "type": "json_object"
            },
        max_tokens=200,
        temperature=0.5
    )
    
    gpt_response=json.loads(response.choices[0].message.content)
    return gpt_response['bad_weather']


#
def confirm_action(user_input, current_step):
    """
    Use GPT to detect if the user confirms or rejects an action.
    For example, locking a location or proceeding with a decision.
    """
    print("inside confirm_action")
    if current_step == 'ask_lock_location' or current_step == 'lock_or_change':
        prompt = f""" The user was asked if they want to lock the location. Based on their input: '{user_input}', does the user want to lock the location?"""
    elif current_step == "end_or_suggest_alternatives":
        prompt = f""" The user was asked if they want to add another visit. Based on their input: '{user_input}', does the user want to add another visit?"""

    prompt += "Return a JSON object with the key 'confirm' and the boolean values of True (for confirmation) or False (for rejection)."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            'role': 'user', 
            'content': prompt
            }],
        response_format={
            "type": "json_object"
            },
        max_tokens=50,
        temperature=0.5
    )

    gpt_response = json.loads(response.choices[0].message.content)
    return gpt_response['confirm']


# [markdown]
# # Bot

#
def orchestrator(user_input, current_step, conversation_state):
    """
    Orchestrates the conversation based on the current step and user input.

    Parameters:
    user_input (str): The input from the user.
    current_step (str): The current step in the conversation.

    Returns:
    str: The next step in the conversation.
    """
    # Define steps of conversation (flow)
    if current_step == "start":
        
        # Get user input and check for details
        detected_info = gpt_extract_info(user_input, current_step, conversation_state)  ### fix gpt response format

        if detected_info["travel_dates"] and detected_info["interests"]:  # If both dates and interests are detected
            conversation_state["travel_dates"] = detected_info["travel_dates"]
            conversation_state["interests"] = detected_info["interests"]
            return "suggest_locations", conversation_state
        
        elif detected_info["travel_dates"]:  # If only dates are detected
            conversation_state["travel_dates"] = detected_info["travel_dates"]
            return "ask_interests", conversation_state
        
        elif detected_info["interests"]:  # If only interests are detected
            conversation_state["interests"] = detected_info["interests"]
        # First step: ask for travel dates
        return "ask_travel_dates", conversation_state
    
    elif current_step == "received_dates":

        if conversation_state.get("interests"):
            # If interests are already detected, suggest locations
            return "suggest_locations", conversation_state
        
        # Next step: ask for interests
        return "ask_interests", conversation_state
    
    elif current_step == "received_interests":
        # save interests
        detected_info = gpt_extract_info(user_input, current_step, conversation_state)              ######### fix gpt response format
        conversation_state["interests"] = detected_info["interests"]

        # Now suggest locations based on interests
        return "suggest_locations", conversation_state
    ########### adding other steps that chatgpt didnt suggest#################
    elif current_step == "received_location":
    # Extract current location or confirm the last suggested one
                ################## here
        curr_loc = gpt_extract_info(user_input, current_step, conversation_state)
        curr_loc=(str(curr_loc['current_location'])+" "+conversation_state['interests'])
        print(curr_loc)
        current_location = db.similarity_search(curr_loc, k=1, filter={'source':'landmark'})
        if current_location:
            # Convert the first Document to a dictionary
            conversation_state["current_location"] = {
                "page_content": current_location[0].page_content,
                "metadata": current_location[0].metadata
            }
        # current_location = gpt_extract_info(user_input, current_step, conversation_state)
        
        if current_location:
            conversation_state["current_location"] = current_location
        
        # Ask if the user accepts the suggested location
        return "ask_accept_location", conversation_state

    elif current_step == "ask_accept_location":
        # Extract user's decision (accept or decline)
        user_decision = gpt_extract_info(user_input, current_step, conversation_state)
        
        if user_decision == "accept":
            # Move forward to lock the location or ask for further details
            return "lock_location", conversation_state
        else:
            # If the user declines, go back and suggest another location
            return "suggest_locations", conversation_state

    elif current_step == "ask_lock_location":
        #after answering questions, ask if user wants to lock in location

        ################################
        want_to_lock = confirm_action(user_input, current_step) ######### fix gpt response format

        #we asked if "they want to go there." if they say yes, we lock in location (temporarily)
        
        if want_to_lock: #if they want to go there...
            # check if location is weather dependant (maybe another gpt call and they respond {"weather dependant": True})
            weather_dependant = is_weather_dependent(conversation_state["current_location"])        # fix gpt response format
            if weather_dependant:
                #check weather for date
                bad_weather = check_weather(conversation_state["current_location"], conversation_state["travel_dates"]) # fix gpt response format
                if bad_weather:
                    return "bad_weather", conversation_state
            else:
                return "lock_location", conversation_state
        # if they say no, we suggest other locations
        else:
            #suggest locations
            return "suggest_locations", conversation_state
            # return "suggest_alternatives" , conversation_state# create new step for this"
    elif current_step == "lock_or_change":
        # there was bad weather and we asked the user if they wanted to lock the location.
        want_to_lock = confirm_action(user_input, current_step)           #########fix gpt response format
        if want_to_lock:
            conversation_state["locked_locations"].append(conversation_state["current_location"])
            return "lock_location", conversation_state
        else:
            return "suggest_alternatives", conversation_state

    elif current_step == "suggest_other_locations":
        # suggest other locations
        return "suggest_locations", conversation_state
    
    elif current_step == "end_or_suggest_alternatives":
        # we asked the user if the would like to go anywhere else
        want_to_go = confirm_action(user_input, current_step)           #########fix gpt response format
        if want_to_go:
            return "suggest_locations", conversation_state
        else:
            return "end_conversation", conversation_state
        
    elif current_step == "return_list_of_locked_locations":
        return "give_list", conversation_state
    ##############################################
    else:
        # Fall back to default
        return "default_response", conversation_state



#
def chat(user_input, instructions ,conversation_state, rag_response = None):
    prompt= f"""
        You are a bot that helps with tourism in Puerto Rico. The user said {user_input}.
        This are some basic instructions for you, to answer to the user {instructions}.
        Please be nice and professional, and keep the flow of the conversation.
    """
    if rag_response:
        prompt += f"Use these RAGs we have for answering: {rag_response}"
        
    message_history = conversation_state.get("messages", [])
    messages = message_history + [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=500,
        temperature=1
    )
    print("inside chat")

    return response.choices[0].message.content

#
def communicator(orchestrator_action, user_input, conversation_state):
    """
    Communicates with the user based on the orchestrator's action.

    Parameters:
    orchestrator_action (str): The action recommended by the orchestrator.
    user_input (str): The input from the user.

    Returns:
    str: The response to the user.
    """
    response = ""

    if orchestrator_action == "ask_travel_dates":
        # Use GPT-4o-mini to rephrase the question
        response= chat(user_input, "ask for the users travel dates", conversation_state)
    elif orchestrator_action == "ask_interests":
        # GPT-4o-mini rephrasing
        response= chat(user_input, "Ask what kind of places do you they want to visit, like beaches, museums or other you want to say", conversation_state)

    elif orchestrator_action == "ask_accept_location":
    # Rephrase the question to the user asking if they want to visit the current location
        current_location = conversation_state.get("current_location", "the suggested location")
        response = chat(user_input, f"Do you want to visit {current_location}? Please answer 'yes' or 'no'.", conversation_state)
        

    elif orchestrator_action == "suggest_locations":
        # Suggest locations based on interests (USE RAG)
        if not conversation_state.get("suggested_locations"):
            rag_response = db.similarity_search(user_input, k=7, filter={'source': 'landmarks'})
            # Convert Document objects to dictionaries
            serialized_locations = [
                {"page_content": doc.page_content, "metadata": doc.metadata}
                for doc in rag_response
            ]
            conversation_state["suggested_locations"] = serialized_locations
           # 
        else:
            # Remove the current location from the list if declined
            current_location = conversation_state.get("current_location")
            conversation_state["suggested_locations"] = [
                loc for loc in conversation_state["suggested_locations"] if loc != current_location
            ]
        
        # GPT-4o-mini rephrasing to suggest locations based on RAG
        response = chat(user_input, "Here is another location you might like: (description of first from RAG). Would you like to visit this one?", conversation_state)
            
   

    elif orchestrator_action == "answer_questions":
        # Answer questions about the location
        info = db.similarity_search(user_input) 
        response = chat(user_input, f"Answer the user's questions about (or simply give info) {conversation_state['current_location']}, and ask if they want to visit.", conversation_state, info)
    elif orchestrator_action == "bad_weather":
        # Inform user about bad weather
        response = chat(user_input, "Inform the user that the weather is bad for their travel dates and ask if they still want to proceed with the location.", conversation_state)
    elif orchestrator_action == "lock_location":
        # Lock the location
                ####### here
        conversation_state["locked_locations"].append(conversation_state["current_location"]) 
        response = chat(user_input, "Confirm that you've locked the selected location for their trip and ask if they want to choose more locations.", conversation_state)
    elif orchestrator_action == "suggest_alternatives":
        # Suggest alternative locations
        response = chat(user_input, "Suggest alternative locations the user might be interested in if the previous location wasn't a good fit.", conversation_state)
    elif orchestrator_action == "end_conversation":
        # End the conversation
        response = chat(user_input, "Thank the user and wish them a great trip. Prepare to end the conversation.", conversation_state)
    elif orchestrator_action == "give_list":
        # Provide the list of locked locations
        lst = str(conversation_state.get("locked_locations", []))
        response = chat(user_input, f"Give the user a list of the locations they have locked in for their trip. The locked locations are {lst}", conversation_state)
    else:
        # Default fallback
        response = chat(user_input, "I'm not sure how to respond to this action. Ask for clarification from the user.", conversation_state)
    
    conversation_state["messages"].append({'role':"user", "content": user_input})
    conversation_state["messages"].append({'role':"system", "content": response})

    print(f"orchestrator_action: {orchestrator_action}")

    return response, conversation_state

#
def cur_step (orchestrator_action):
     # Update the flow based on the orchestrator's action
    if orchestrator_action == "ask_travel_dates":
        return "received_dates"
    elif orchestrator_action == "ask_interests":
        return "received_interests"
    elif orchestrator_action == "suggest_locations":
        #########################
        return "received_location"
    elif orchestrator_action == "answer_questions":
        return "ask_lock_location"
    elif orchestrator_action == "bad_weather":
        return "lock_or_change"
    elif orchestrator_action == "lock_location":
        return "end_or_suggest_alternatives"

    elif orchestrator_action == "suggest_alternatives":
        return "suggest_other_locations"
    elif orchestrator_action == "end_conversation":
        return "return_list_of_locked_locations"
    elif orchestrator_action == "give_list":  
        return "end"
    return "default_response"


# current_step = "start"
#######################

def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return "Shutting down..."

app.secret_key = '5678'

def get_completion(user_input, current_step, conversation_state):
    if current_step != "end":
        # user_input = input("You (tye 'exit' to close): ")  # Get user input
        if user_input == "":
            return
        if(user_input == "exit"):
            shutdown()
        
        print(f"> {user_input}")
        print("Current step:", current_step)

        orchestrator_action, conversation_state = orchestrator(user_input, current_step, conversation_state)
        response, conversation_state = communicator(orchestrator_action, user_input, conversation_state)
        
        
        # Update the flow based on the orchestrator's action
        if orchestrator_action == "ask_travel_dates":
            current_step = "received_dates"
        elif orchestrator_action == "ask_interests":
            current_step = "received_interests"
        elif orchestrator_action == "suggest_locations":
            #########################
            current_step = "received_location"
        elif orchestrator_action == "ask_accept_location":
            current_step = "ask_lock_location"
            # current_step = "ask_accept_location"        #ask lock location

        elif orchestrator_action == "bad_weather":
            current_step = "lock_or_change"
        elif orchestrator_action == "lock_location":
            current_step = "end_or_suggest_alternatives"

        elif orchestrator_action == "suggest_alternatives":
            current_step = "suggest_other_locations"
        elif orchestrator_action == "end_conversation":
            current_step = "return_list_of_locked_locations"
        elif orchestrator_action == "give_list":  
            current_step = "end"

        session['orchestrator_action'] = orchestrator_action

        return response, current_step, conversation_state #, orchestrator_action




########################################################################################################################
@app.route("/")
def home():    
    return render_template("index.html")

@app.route("/get")
def get_bot_response():    
    userText = request.args.get('msg')  
    current_step = session.get('current_step', 'start')
    conversation_state = session.get('conversation_state', {
        "travel_dates": None,
        "interests": None,
        "locked_locations": [],  # Already serializable
        "suggested_locations": [],  # Now stores dictionaries
        "current_location": None,
        "messages": []
    })

    response, current_step, conversation_state = get_completion(userText, current_step, conversation_state)  
    #return str(bot.get_response(userText)) 
    # current_step = cur_stp
    # conversation_state = conv_state
    # Update the session with the new conversation state and step
    session['current_step'] = current_step
    session['conversation_state'] = conversation_state

    return response
if __name__ == "__main__":
    app.run(debug=True)