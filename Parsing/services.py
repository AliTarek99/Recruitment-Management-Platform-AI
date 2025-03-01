import pdfplumber
import re
import json
from groq import Groq
from decouple import config
import io
from minio import Minio
import asyncpg
from groq import AsyncGroq
from aiobotocore.session import get_session
pool = None

client = AsyncGroq(

    api_key= config("GROQ_API_KEY"),

)


async def run():
    # Establish a connection to the database
    global pool
    pool = await asyncpg.create_pool(
        host = config("DB_HOST"), 
        database=config("DB_NAME"), 
        user=config("DB_USER"), 
        password=config("DB_PASSWORD"),
        port=config("DB_PORT"),
        min_size=int(config("DB_POOL_MIN_SIZE")),
        max_size=int(config("DB_POOL_MAX_SIZE"))
    )

def extract_text_from_pdf(pdf_bytes):
    text = ""
    with pdfplumber.open(pdf_bytes) as pdf:
        for page in pdf.pages:
            text = page.extract_text() + "\n"
    return text

async def parse(id, cv=None):
    global pool
    if pool == None:
        await run()
    session = get_session()
    pdf_text = ""
    if not cv:
        async with session.create_client(
            's3',
            endpoint_url=config("MINIO_ENDPOINT"),
            aws_access_key_id=config("MINIO_ACCESS_KEY"),
            aws_secret_access_key=config("MINIO_SECRET_KEY"),
        ) as minio_client:
            response = await minio_client.get_object(Bucket=config("MINIO_CV_BUCKET"), Key=f"{id}.pdf")
            pdf_bytes = io.BytesIO((await response.get("Body").read()))
    else:
        pdf_bytes = io.BytesIO(cv)
    pdf_text = extract_text_from_pdf(pdf_bytes)
	
    prompt = '''You are an AI assistant specialized in extracting structured information from resumes. Given the following resume text, extract key details in exactly this JSON format. Here's an example:

	{
	"contactInformation": {
		"name": "Full Name",
		"phone": "Phone Number",
		"email": "Email Address",
		"location": "City, Country"
	},
	"education": [
		{
		"degree": "Degree Name",
		"university": "University Name",
		"faculty": "Faculty Name",
		"start Year": "Start Year",
		"End Year": "End Year",
		"grade": "provided grade"
		}
	],
	"workExperience": [
		{
		"title": "Job Title",
		"company": "Company Name",
		"start date": "Month Year",
		"end date": "Month Year"
		}
	],
	"skills": [
		"Skill 1",
		"Skill 2",
		"Skill 3"
	],
	"spoken languages": [
		"Language 1",
		"Language 2"
	]
	}

	### **Instructions (Follow Strictly):**
	1. **Maintain the exact JSON structure with correct nesting**. This is a **top priority**.  
	2. **Extract all available information while ensuring accuracy**.  
	3. **Format Dates**: Use `Month Year` format for both start and end dates (e.g., `"January 2022 - December 2023"`).  
	4. **Format Locations**: Use `City, Country` format (e.g., `"San Francisco, USA"`).  
	5. **Spoken Languages**: Include **only** the language names (e.g., `"English"`, `"Spanish"`).  
	6. **Skills**: 
		- Extract and list **all relevant skills**. Check for skills **in any section of the CV**, not just in a dedicated "Skills" section.
		-Ensure each individual skill is added as a separate element in the "skills" list.
	7. **Grade (GPA Handling)**:
	- If a GPA is provided, extract **only the numeric GPA** (e.g., `"3.48"` from `"GPA: 3.48 of 4.00"`).  
	- Do **not** include text like `"of 4.00"` or `"%"`.  
	- If the GPA is not explicitly available, check for a percentage (e.g., `"85%" → `"85"`).  
	- If no grade is found, leave it **blank**.  
	8. **Abbreviations**: Expand common abbreviations into their full form. Example:
	- `"ML"` → `"Machine Learning"`
	- `"NLP"` → `"Natural Language Processing"`
	- `"AI"` → `"Artificial Intelligence"`
	9. **If a field is missing, leave it blank** instead of guessing.  
	10. **Output only valid JSON**:  
	- **Do not include any introductory/explanatory text.**  
	- **Do not print `json` or any formatting hints before the JSON output.**
	11. **Phone Numbers**: If multiple phone numbers are found, include only the most relevant one (e.g., the primary number mentioned under contact details or the first valid number found). Ignore duplicates or secondary numbers.
	'''

    conversation =[
		{
			"role":"system",
			"content": prompt
		},
		{
			"role":"user",
			"content": f"Extract structured information from this resume:\n\n{pdf_text}"
		}
	]

    CV_query = await client.chat.completions.create(

		messages=conversation,

		model="llama-3.3-70b-versatile",

	)

    CV_response = CV_query.choices[0].message.content

    parsed_CV = re.search(r'```\s*(?:json)?\s*(.*?)```', CV_response, re.DOTALL)
    
    extracted_CV = None
    
    if parsed_CV:
        extracted_CV = parsed_CV.group(1).strip()
    else:
        extracted_CV = CV_response

	# handle grpc call
    if cv:
        return extracted_CV
    # handle consuming from kafka
    else:
        CV_dict = json.loads(extracted_CV)
        async with pool.acquire() as conn:
            await conn.fetch("INSERT INTO cv_keywords (cv_id, skills) VALUES($1, $2) ON CONFLICT (cv_id) DO NOTHING", id, CV_dict.get("skills"))
    