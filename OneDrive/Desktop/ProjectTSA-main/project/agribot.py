import openai

# Set your OpenAI API key
openai.api_key = "GPT"

def get_response(prompt, chat_history):
    model = "gpt-3.5-turbo"  # Cheapest chat model in the OpenAI API

    try:
        # Call the OpenAI API with the chat model
        print(f"Using model: {model}")
        response = openai.ChatCompletion.create(  # Corrected to use `ChatCompletion`
            model=model,
            messages=chat_history  # Send the entire chat history
        )

        # Extract the bot's response
        bot_response = response['choices'][0]['message']['content']
        chat_history.append({"role": "assistant", "content": bot_response})  # Append the bot's response to history
        return bot_response

    except Exception as e:
        print(f"An error occurred: {e}")
        return "An error occurred. Please try again later."


def agribot_(user_input):
    # Initial chat history with a system prompt
    chat_history = [
        {"role": "system", "content": "You are an expert in agriculture and provide information about crops. Answers should be short"},
    ]

    # Append user input to chat history
    chat_history.append({"role": "user", "content": user_input})

    # Get response from the chatbot
    response = get_response(user_input, chat_history)
    return response
