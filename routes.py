
import logging
import json
import requests
import uuid
from flask import request, render_template, redirect, url_for, jsonify, flash
from app import app

# Monday.com API configuration
MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjQxMDM1MDMyNiwiYWFpIjoxMSwidWlkIjo1NTIyMDQ0LCJpYWQiOiIyMDI0LTA5LTEzVDExOjUyOjQzLjAwMFoiLCJwZXIiOiJtZTp3cml0ZSIsImFjdGlkIjozNzk1MywicmduIjoidXNlMSJ9.hwTlwMwtbhKdZsYcGT7UoENBLZUAxnfUXchj5RZJBz4"
BOARD_ID = "9241811459"

# In-memory storage for survey data (temporary until submitted to Monday.com)
surveys = {}

def monday_graphql_request(query, variables=None):
    """Make a GraphQL request to Monday.com API"""
    headers = {
        "Authorization": f"Bearer {MONDAY_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": query,
        "variables": variables or {}
    }

    response = requests.post(MONDAY_API_URL, json=payload, headers=headers)
    return response.json()

def get_item_data(item_id):
    """Fetch item data including Date and Location columns"""
    query = """
    query($itemId: [ID!]) {
        items(ids: $itemId) {
            id
            name
            column_values {
                id
                text
                value
                ... on MirrorValue {
                    display_value
                }
            }
        }
    }
    """

    variables = {
        "itemId": [str(item_id)]
    }

    result = monday_graphql_request(query, variables)
    return result

def update_survey_link(item_id, survey_url):
    """Update the link column with survey URL"""
    query = """
    mutation($itemId: ID!, $boardId: ID!, $columnId: String!, $value: JSON!) {
        change_column_value(
            item_id: $itemId, 
            board_id: $boardId, 
            column_id: $columnId, 
            value: $value
        ) {
            id
        }
    }
    """

    variables = {
        "itemId": str(item_id),
        "boardId": BOARD_ID,
        "columnId": "text_mkrb8f7",
        "value": f'"{survey_url}"'
    }

    result = monday_graphql_request(query, variables)
    return result

def create_survey_result_item(trip_name, nps_score, location, feedback=""):
    """Create a new item with survey results"""
    query = """
    mutation($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item(
            board_id: $boardId,
            item_name: $itemName,
            column_values: $columnValues
        ) {
            id
            name
        }
    }
    """

    column_values = {
        "numeric_mkrba1c4": nps_score,
        "text_mkrb17ct": location,
        "text_mkrb96zz": trip_name
    }

    # Add feedback if provided
    if feedback:
        column_values["text__1"] = feedback  # Adjust column ID as needed

    variables = {
        "boardId": "9242892489",
        "itemName": "Nova avaliação",
        "columnValues": json.dumps(column_values)
    }

    result = monday_graphql_request(query, variables)
    return result

@app.route('/webhook/monday', methods=['GET', 'POST'])
def monday_webhook():
    """Handle Monday.com webhook with challenge response"""

    if request.method == 'GET':
        # Handle challenge verification
        challenge = request.args.get('challenge')
        if challenge:
            logging.info(f"GET challenge received: {challenge}")
            return challenge, 200, {'Content-Type': 'text/plain'}
        return "Webhook endpoint ready", 200

    elif request.method == 'POST':
        try:
            # Parse webhook data
            data = request.get_json()
            logging.info(f"Webhook data received: {data}")

            # Handle challenge response for POST requests
            if 'challenge' in data:
                challenge = data['challenge']
                print("Received challenge:", challenge)
                return jsonify({'challenge': challenge}), 200

            # Extract basic info from webhook
            event_data = data.get('event', {})
            pulse_id = event_data.get('pulseId')
            trip_name = event_data.get('pulseName', 'Unknown Trip')

            if not pulse_id:
                return jsonify({"error": "No pulse ID found"}), 400

            # Fetch complete item data using GraphQL
            print(f"Fetching data for item ID: {pulse_id}")
            item_data_response = get_item_data(pulse_id)

            if 'errors' in item_data_response:
                print(f"GraphQL error: {item_data_response['errors']}")
                location = "Unknown Location"
                date = "Unknown Date"
                company_name = "Unknown Company"
            else:
                items = item_data_response.get('data', {}).get('items', [])
                if items:
                    item = items[0]
                    column_values = item.get('column_values', [])

                    # Extract location, date, and company name from specific columns
                    location = "Unknown Location"
                    date = "Unknown Date"
                    company_name = "Unknown Company"

                    for col in column_values:
                        print(f"Column ID: {col['id']}, Text: {col.get('text')}, Value: {col.get('value')}")

                        if col['id'] == 'text_mkrb3wyx':  # Location column
                            location = col.get('text') or "Unknown Location"
                        elif col['id'] == 'data':  # Date column
                            date = col.get('text') or "Unknown Date"
                        elif col['id'] == 'lookup_mkrb9ns5':  # Mirror column lookup for company
                            # Mirror columns use display_value field
                            display_value = col.get('display_value')
                            if display_value:
                                company_name = display_value
                            else:
                                # Fallback to text or value
                                company_name = col.get('text') or col.get('value') or "Unknown Company"
                            print(f"Mirror column display_value: {display_value}")
                            print(f"Mirror column text: {col.get('text')}")
                            print(f"Mirror column value: {col.get('value')}")
                            print(f"Company name extracted: {company_name}")

                    print(f"Extracted - Location: {location}, Date: {date}, Company: {company_name}")
                else:
                    print("No items found in GraphQL response")
                    location = "Unknown Location"
                    date = "Unknown Date"
                    company_name = "Unknown Company"

            # Generate unique survey ID
            survey_id = str(uuid.uuid4())

            # Store survey data in memory
            surveys[survey_id] = {
                'survey_id': survey_id,
                'location': location,
                'date': date,
                'trip_name': trip_name,
                'company_name': company_name,
                'pulse_id': pulse_id
            }

            # Generate survey URL
            survey_url = url_for('survey_form', survey_id=survey_id, _external=True)

            # Update Monday.com with survey link
            print(f"Updating Monday.com item {pulse_id} with survey link")
            update_result = update_survey_link(pulse_id, survey_url)

            if 'errors' in update_result:
                print(f"Error updating Monday.com: {update_result['errors']}")
            else:
                print("Successfully updated Monday.com with survey link")

            # Log the survey page link to console
            print(f"\n{'='*60}")
            print(f"NEW SURVEY CREATED!")
            print(f"Survey ID: {survey_id}")
            print(f"Location: {location}")
            print(f"Date: {date}")
            print(f"Trip Name: {trip_name}")
            print(f"Company Name: {company_name}")
            print(f"Survey URL: {survey_url}")
            print(f"Monday.com Item ID: {pulse_id}")
            print(f"{'='*60}\n")

            return jsonify({
                "status": "success",
                "survey_id": survey_id,
                "survey_url": survey_url
            }), 200

        except Exception as e:
            logging.error(f"Error processing webhook: {str(e)}")
            return jsonify({"error": "Failed to process webhook"}), 500

@app.route('/survey/<survey_id>')
def survey_form(survey_id):
    """Display the NPS survey form"""
    survey = surveys.get(survey_id)

    if not survey:
        return "Pesquisa não encontrada", 404

    return render_template('survey.html', survey=survey)

@app.route('/survey/<survey_id>/submit', methods=['POST'])
def submit_survey(survey_id):
    """Handle survey submission"""
    survey = surveys.get(survey_id)

    if not survey:
        return "Pesquisa não encontrada", 404

    try:
        nps_score = int(request.form.get('nps_score'))
        feedback = request.form.get('feedback', '').strip()

        # Validate NPS score
        if nps_score < 0 or nps_score > 10:
            flash("Por favor, selecione uma avaliação válida entre 0 e 10.", "error")
            return redirect(url_for('survey_form', survey_id=survey_id))

        # Create new item in Monday.com with survey results
        print(f"Creating Monday.com item for survey results")
        monday_result = create_survey_result_item(
            survey['trip_name'], 
            nps_score, 
            survey['location'],
            feedback
        )

        if 'errors' in monday_result:
            print(f"Error creating Monday.com item: {monday_result['errors']}")
            flash("Erro ao salvar resposta. Tente novamente.", "error")
            return redirect(url_for('survey_form', survey_id=survey_id))
        else:
            created_item = monday_result.get('data', {}).get('create_item', {})
            print(f"Successfully created Monday.com item: {created_item.get('id')}")

        # Log completion to console
        print(f"\n{'='*60}")
        print(f"SURVEY COMPLETED!")
        print(f"Survey ID: {survey_id}")
        print(f"Trip: {survey['trip_name']}")
        print(f"Location: {survey['location']}")
        print(f"NPS Score: {nps_score}")
        print(f"Feedback: {feedback if feedback else 'No feedback provided'}")
        print(f"{'='*60}\n")

        flash("Obrigado pelo seu feedback!", "success")
        return redirect(url_for('thank_you', survey_id=survey_id))

    except (ValueError, TypeError):
        flash("Por favor, selecione uma avaliação válida.", "error")
        return redirect(url_for('survey_form', survey_id=survey_id))
    except Exception as e:
        logging.error(f"Error submitting survey: {str(e)}")
        flash("Ocorreu um erro ao enviar sua resposta. Por favor, tente novamente.", "error")
        return redirect(url_for('survey_form', survey_id=survey_id))

@app.route('/survey/<survey_id>/thank-you')
def thank_you(survey_id):
    """Display thank you page"""
    survey = surveys.get(survey_id)

    if not survey:
        return "Pesquisa não encontrada", 404

    return render_template('thank_you.html', survey=survey)

@app.route('/')
def index():
    """Home page"""
    return """
    <html>
    <head>
        <title>Sistema de Pesquisa NPS de Viagem</title>
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                padding: 50px;
                margin: 0;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-direction: column;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            }
            h1 { font-size: 3em; margin-bottom: 20px; }
            p { font-size: 1.2em; opacity: 0.9; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🌍 Sistema de Pesquisa NPS de Viagem</h1>
            <p>Endpoint webhook pronto para receber dados do Monday.com</p>
            <p>Pesquisas serão geradas automaticamente quando webhooks forem recebidos</p>
        </div>
    </body>
    </html>
    """

@app.errorhandler(404)
def not_found_error(error):
    return render_template('thank_you.html', survey=None, error="Página não encontrada"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('thank_you.html', survey=None, error="Erro interno do servidor"), 500
