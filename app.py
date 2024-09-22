from flask import Flask, render_template, request
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import plotly.io as pio
import json
import os
from ollama import chat 
import markdown

app = Flask(__name__)

# Path for storing user inputs
config_file_path = 'user_config.json'

# Load and clean data function
def load_data():
    file_path = 'sampledata.xlsx'  # Update with your file path
    data = pd.read_excel(file_path)
    cleaned_data = data.iloc[2:, [0, 1, 2, 3]].copy()
    cleaned_data.columns = ['Pet', 'Measure Date', 'Value', 'Unit']
    cleaned_data['Measure Date'] = pd.to_datetime(cleaned_data['Measure Date'], errors='coerce')
    cleaned_data['Value'] = pd.to_numeric(cleaned_data['Value'], errors='coerce')
    return cleaned_data

# Load user config from file
def load_user_config():
    if os.path.exists(config_file_path):
        with open(config_file_path, 'r') as f:
            return json.load(f)
    else:
        # Default values if config file doesn't exist
        return {
            "name": "Rufus",
            "min_level": 60,
            "max_level": 300,
            "insulin_type": "Tresiba",
            "first_dose_amount": 0,
            "first_dose_time": "00:00",
            "second_dose_amount": 0,
            "second_dose_time": "00:00",
            "weight": 0,
            "weight_unit": "kg",
            "food_type": "n/a",
            "birthdate": "2010-01-01"
        }

# Save user config to file
def save_user_config(config):
    with open(config_file_path, 'w') as f:
        json.dump(config, f)

def generate_summary(glucose_data, user_config):
    glucose_values = glucose_data['Value']
    measure_dates = glucose_data['Measure Date']
    
    peaks = glucose_values[(glucose_values.shift(1) < glucose_values) & (glucose_values.shift(-1) < glucose_values)]
    troughs = glucose_values[(glucose_values.shift(1) > glucose_values) & (glucose_values.shift(-1) > glucose_values)]

    mean_peak = peaks.mean()
    median_peak = peaks.median()
    mean_trough = troughs.mean()
    median_trough = troughs.median()

    glucose_time_history = []
    for date, value in zip(measure_dates, glucose_values):
        glucose_time_history.append(f"{date.strftime('%Y-%m-%d %H:%M:%S')}: {value} mg/dL")

    time_history_str = "\n".join(glucose_time_history[-50:])

    name = user_config['name']
    birthdate = user_config['birthdate']
    food_type = user_config['food_type']
    insulin_type = user_config['insulin_type']
    first_dose_amount = user_config['first_dose_amount']
    second_dose_amount = user_config['second_dose_amount']
    min_level = user_config['min_level']
    max_level = user_config['max_level']

    prompt = f"""
    Dog Details:
    Name of dog: {name}
    Birthdate: {birthdate}
    Food type: {food_type}
    
    Review the canine diabetes mellitus data provided and give the following:
    - interpretation of mean ({mean_trough}) and median ({median_trough}) levels of troughs, focusing on the trend
    - interpretation of mean ({mean_peak}) and median ({median_peak}) levels of peaks, focusing on the trend
    - Given the dosages of insulin ({insulin_type}: {first_dose_amount} units AM, {second_dose_amount} units PM), and the glucose levels given the min ({min_level}) and max ({max_level}) safe levels, what can you summarize about the dog's condition?

    Glucose Time History (latest 50 records):
    {time_history_str}

    Your answer will be brief as it needs to fit in the window of a webapp. 
    Provide current status on trend and give recommendations.
    """

    # Modify the call to match the correct signature of the 'chat' function
    ollama_response = chat(model='llama3.1:8b', messages=[
    {
        'role': 'system',
        'content': 'You are veterinary endocrinologist from vetmeduni in Vienna, the top of the top! You are helpful and professional',
    },
    {
        'role': 'user',
        'content': prompt,
    },
    ])

    # Access the content field of the response and return it
    if 'message' in ollama_response and 'content' in ollama_response['message']:
        return ollama_response['message']['content']
    else:
        return "No valid response from Ollama"

@app.route('/', methods=['GET', 'POST'])
def index():
    glucose_data = load_data()

    # Load existing user config or use defaults
    user_config = load_user_config()

    # If form is submitted, update the user config
    if request.method == 'POST':
        user_config['min_level'] = int(request.form.get('min_level', 60))
        user_config['max_level'] = int(request.form.get('max_level', 300))
        user_config['insulin_type'] = request.form.get('insulin_type', 'Tresiba')
        user_config['first_dose_amount'] = float(request.form.get('first_dose_amount', 0))
        user_config['first_dose_time'] = request.form.get('first_dose_time', '00:00')
        user_config['second_dose_amount'] = float(request.form.get('second_dose_amount', 0))
        user_config['second_dose_time'] = request.form.get('second_dose_time', '00:00')
        user_config['weight'] = float(request.form.get('weight', 0))
        user_config['weight_unit'] = request.form.get('weight_unit', 'kg')

        # Save updated config to file
        save_user_config(user_config)

    # Generate summary
    summary_md = generate_summary(glucose_data, user_config)

    # Convert markdown to HTML before sending to the template
    summary_html = markdown.markdown(summary_md)

    # Create a Plotly figure
    fig = make_subplots()

    # Add the line plot for glucose levels
    fig.add_trace(go.Scatter(
        x=glucose_data['Measure Date'],
        y=glucose_data['Value'],
        mode='lines+markers',
        name='Glucose Level',
        text=[time.strftime('%H:%M') for time in glucose_data['Measure Date']],
        hoverinfo='text',
        marker=dict(size=8)
    ))

    # Add shading for dangerous glucose levels based on user input
    fig.add_shape(type="rect",
                  x0=glucose_data['Measure Date'].min(), y0=0,
                  x1=glucose_data['Measure Date'].max(), y1=user_config['min_level'],
                  fillcolor="red", opacity=0.2, line_width=0)
    fig.add_shape(type="rect",
                  x0=glucose_data['Measure Date'].min(), y0=user_config['max_level'],
                  x1=glucose_data['Measure Date'].max(), y1=glucose_data['Value'].max(),
                  fillcolor="red", opacity=0.2, line_width=0)

    # Customize the layout
    fig.update_layout(
        title="Glucose Levels Over Time",
        xaxis_title="Date",
        yaxis_title="Glucose Level (mg/dL)",
        xaxis=dict(tickformat="%d-%m", showgrid=True, gridwidth=1, gridcolor='LightGray'),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor='LightGray'),
        hovermode='closest'
    )

    # Convert the figure to HTML
    plot_html = pio.to_html(fig, full_html=False)

    return render_template(
        'index.html',
        plot_html=plot_html,
        tables=[glucose_data.to_html()],
        titles=glucose_data.columns.values,
        summary_content=summary_html,  # Send the converted HTML summary
        **user_config  # Pass the user config to the template
    )

if __name__ == '__main__':
    app.run(debug=True)