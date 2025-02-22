from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai
import os
from dotenv import load_dotenv
import MySQLdb
import re
load_dotenv()
app = FastAPI(
    title="Memo Generator with AI",
    description="API for generating and updating memorandum sections using OpenAI."
)
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()
def get_db_connection():
    try:
        connection = MySQLdb.connect(
            host="localhost",
            user="root",
            password="",
            database="memo"
        )
        return connection
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
class MemoRequest(BaseModel):
    subject: str

class MemoUpdateRequest(BaseModel):
    instruction: str
    field_to_update: str

class MemoResponse(BaseModel):
    background: str
    proposal: str
    recommendation: str
def get_existing_memo(id: int) -> dict:
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        query = "SELECT subject, background, proposal, recommendation FROM memo_m WHERE id = %s"
        cursor.execute(query, (id,))
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        if not result:
            raise HTTPException(status_code=404, detail="Memo with the specified id not found.")
        return {
            "subject" : result[0],
            "background": result[1],
            "proposal": result[2],
            "recommendation": result[3]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching memo: {str(e)}")
    
def store_in_database(subject, background, proposal, recommendation):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        insert_query = """
        INSERT INTO memo_m (subject, background, proposal, recommendation, last_updated)
        VALUES (%s, %s, %s, %s, NOW())
        """
        cursor.execute(insert_query, (subject, background, proposal, recommendation))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing memo: {str(e)}")
    
def update_memo_in_database(id, field_to_update, new_content):
    valid_fields = ['background', 'proposal', 'recommendation']
    if field_to_update not in valid_fields:
        raise HTTPException(status_code=400, detail="Invalid field to update. Must be 'background', 'proposal', or 'recommendation'.")
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        update_query = f"UPDATE memo_m SET {field_to_update} = %s, last_updated = NOW() WHERE id = %s"
        cursor.execute(update_query, (new_content, id))
        connection.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="no such row.")

        cursor.close()
        connection.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating memo: {str(e)}")

def generate_updated_content(existing_sections: dict, field_to_update: str,instruction:str) -> str:
    context = f"""
    The subject of this memo is: '{existing_sections['subject']}'.
    
    Current sections of the memo are as follows:
    ### 1. Background
    {existing_sections['background']}

    ### 2. Proposal
    {existing_sections['proposal']}

    ### 3. Recommendation
    {existing_sections['recommendation']}

    Update the '{field_to_update}' section only by making changes with {instruction} . Ensure the updated content aligns with the context of the other sections and the subject. Provide only the content for the '{field_to_update}' section.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional memorandum writer."},
                {"role": "user", "content": context}
            ]
        )
        content = response.choices[0].message.content.strip()
        print(content)
        background = extract_section(content, "1. Background")
        proposal = extract_section(content, "2. Proposal")
        recommendation = extract_section(content, "3. Recommendation")
        if field_to_update == 'background':
            return background
        if field_to_update == 'proposal':
            return proposal
        if field_to_update == 'recommendation':
            return recommendation
        
        if not content:
            raise HTTPException(status_code=500, detail="No content returned from OpenAI.")

        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating updated content: {str(e)}")

@app.post("/generate-memo/", response_model=MemoResponse)
async def generate_memorandum(request: MemoRequest):
    subject = request.subject
    prompt = f"""
    You are tasked with drafting a formal memo for the bank based on the subject: '{subject}'. 
    The memo should strictly include the following three sections, formatted as follows:

    ### 1. Background
    Provide a detailed overview of the context and relevant background information that led to the necessity of this memo.

    ### 2. Proposal
    Present the proposed course of action, addressing key objectives and strategies.

    ### 3. Recommendation
    Offer actionable recommendations based on the analysis in the Background and Proposal sections.

    Do not include any additional sections such as 'To', 'From', 'Subject', or 'Objective'. 
    Ensure the content is concise, formal, and professional.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional business document writer."},
                {"role": "user", "content": prompt}
            ]
        )
        
        content = response.choices[0].message.content.strip()
        background = extract_section(content, "1. Background")
        proposal = extract_section(content, "2. Proposal")
        recommendation = extract_section(content, "3. Recommendation")
        store_in_database(subject, background, proposal, recommendation)

        return MemoResponse(
            background=background,
            proposal=proposal,
            recommendation=recommendation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating memo: {str(e)}")

@app.put("/update-memo/{id}/")
async def update_memorandum(id :int, request: MemoUpdateRequest):
    existing_sections = get_existing_memo(id)
    updated_content = generate_updated_content(existing_sections, request.field_to_update,request.instruction)
    update_memo_in_database(id, request.field_to_update, updated_content)
    return {"message": f"'{request.field_to_update}' section updated successfully updated", f"{request.field_to_update}": updated_content}

def extract_section(content: str, section_title: str) -> str:
    pattern = rf"### {section_title}\n*(.*?)(?=\n###|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
