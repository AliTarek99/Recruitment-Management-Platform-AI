import pdfplumber
from groq import AsyncGroq
import json
import io
from minio import Minio
import asyncpg
from sentence_transformers import SentenceTransformer
from decouple import config
import constants
import re

pool = None 
client_minio = Minio(
    endpoint= config("MINIO_ENDPOINT"),
    access_key= config("MINIO_ACCESS_KEY"),
    secret_key= config("MINIO_SECRET_KEY"),
    secure=False
)

client = AsyncGroq(

    api_key= config("GROQ_API_KEY"),

)

model = SentenceTransformer(config("SENTENCE_TRANSFORMER_MODEL"))

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

def weighted_embed_vec(skill_dict, embedding):
    total_weight = sum(skill_dict.values())
    weighted_sum = sum(embedding[skill] * weight for skill,weight in skill_dict.items())
    return weighted_sum/total_weight

def get_embeddings(skills_dict):
    skills_embed = {skill: model.encode(skill) for skill,weight in skills_dict.items()}
    weighted_embed = weighted_embed_vec(skills_dict, skills_embed)
    return weighted_embed

async def main_function(id,user_id,type):
    global pool
    if pool == None:
        print("Creating database connection pool", flush=True)
        await run()
        print("Database connection pool created", flush=True)
    async with pool.acquire() as conn:
        print(7)
        if type == constants.CV_TYPE:

            rows = await conn.fetch("SELECT skills FROM CV_Keywords WHERE cv_id = $1", id)
            skills = rows[0][0]
            response = client_minio.get_object(config("MINIO_CV_BUCKET"), f"{id}.pdf")
            pdf_bytes = io.BytesIO(response.read())
            text = ""
            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    text += page.extract_text()
                    print(text)
            
            weight_cv = constants.CV_EMBEDDING_PROMPT + text + '''\n \n Extracted Skills: \n''' + f'''{skills}'''
            print(8)
            cv_weighting_conversation = [
                {
                    "role": "system",
                    "content": weight_cv
                },
                {
                    "role": "user",
                    "content": f"Analyze the following CV and extracted skills and return the JSON response.\n\nCV:\n{text}\n\nExtracted Skills:\n{skills}"
                }
            ]
            CV_weight_query = await client.chat.completions.create(

                messages=cv_weighting_conversation,

                model="llama-3.3-70b-versatile",

            )
            print(9)
            CV_weight = CV_weight_query.choices[0].message.content
            match = re.search(r'```\s*(?:json)?\s*(.*?)```', CV_weight, re.DOTALL)
            #If a match is found, apply the regular expression, else, return the original response.
            CV_weight = match.group(1).strip() if match else CV_weight #Failsafe for inconsistent LLM output
            skills_dict_cv = json.loads(CV_weight)

            weighted_cv_embedding = get_embeddings(skills_dict_cv['skills'])

            await conn.fetch("insert into cv_embedding(cv_id,vector) values ($1,$2) on conflict (cv_id) do nothing;",id,f'{weighted_cv_embedding.tolist()}')

        elif type == constants.JOB_TYPE:
            rows = await conn.fetch('''select json_object_agg(skills.name,job_skill.importance) 
                        from job_skill 
                        join skills on job_skill.skill_id = skills.id
                        where job_skill.job_id = $1''',id)
            skills = json.loads(rows[0][0])
            weighted_job_embedding = get_embeddings(skills)
            await recommend_users(id, weighted_job_embedding.tolist(), conn)
            await conn.fetch("insert into job_embedding(job_id,embedding) values ($1,$2) on conflict (job_id) do nothing;",id,f'{weighted_job_embedding.tolist()}')

        if type == constants.PROFILE_TYPE or type == constants.CV_TYPE:
            print("Processing profile or CV type", flush=True)
            cv_id = None

            
            rows = await conn.fetch('''select array_agg(json_build_object(
                        "school_name",education.school_name,
                        "field", education.field, 
                        "degree",education.degree,
                        "grade",education.grade))
                        from education
                        where education.user_id =$1''',user_id)
            education = rows[0][0]
    
            print("Education fetched", flush=True)
            
            rows = await conn.fetch('''select array_agg(json_build_object(
                        "company_name",user_experience.company_name,
                        "start_date",user_experience.start_date,
                        "end_date",user_experience.end_date,
                        "description",user_experience.description,
                        "job_title",user_experience.job_title))
                        from user_experience
                        where user_experience.user_id = $1''',user_id)
            experience = rows[0][0]

            print("Experience fetched", flush=True)

            rows = await conn.fetch('''select array_agg(skills.name)
                        from user_skills
                        join skills on user_skills.skill_id = skills.id
                        where user_skills.user_id = $1''',user_id)
            skills = rows[0][0]

            print("Skills fetched", flush=True)

            if type == 'cv':
                cv_id = id
            else:
                print("Fetching CV ID for user", user_id, flush=True)
                rows = await conn.fetch('''select id
                            from CV
                            where user_id = $1 and deleted = false and created_at = (select max(created_at) from (select created_at from cv where user_id= $1))
                            ''',user_id)
                cv_id = rows[0][0]

            cv = client_minio.get_object(config("MINIO_CV_BUCKET"), f"{cv_id}")

            print("CV fetched from MinIO", flush=True)

            pdf_bytes = io.BytesIO(cv.read())
            cv_text = ""
            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    cv_text += page.extract_text()
            
            print("CV text extracted", flush=True)

            weight_profile = constants.PROFILE_WEIGHING_PROMPT
            profile_conversation = [
                {
                    "role":"system",
                    "content": weight_profile
                },
                {
                    "role":"user",
                    "content":f"Now, analyze the following CV and extracted skills, experience, and education then return the JSON response.\nCV:\n{cv_text}\n\nExtracted Skills:\n{skills}\n\nExtracted Experience:\n{experience}\n\nExtracted Education:\n{education}"
                }
            ]
            profile_weight_query = await client.chat.completions.create(

                messages=profile_conversation,

                model="llama-3.3-70b-versatile",

            )

            profile_weight = profile_weight_query.choices[0].message.content
            print(profile_weight, flush=True)
            match = re.search(r'```\s*(?:json)?\s*(.*?)```', profile_weight, re.DOTALL)
            #If a match is found, apply the regular expression, else, return the original response.
            profile_weight = match.group(1).strip() if match else profile_weight #Failsafe for inconsistent LLM output
            skills_dict_profile = json.loads(profile_weight)

            print("Profile weighting completed", flush=True)

            weighted_profile_embedding = get_embeddings(skills_dict_profile['skills'])
            print("Weighted profile embedding calculated", flush=True)

            await recommend_jobs(user_id, weighted_profile_embedding.tolist(),conn)
            await conn.fetch('''insert into job_seeker_embeddings(seeker_id,embedding) values ($1,$2) 
                            on conflict (seeker_id) do update set embedding = excluded.embedding;''',user_id,f'{weighted_profile_embedding.tolist()}')
            print("Profile embedding inserted into database", flush=True)


async def recommend_jobs(user_id, embedding, conn):
    print("Recommending jobs for user:", user_id, flush=True)
    await conn.fetch('''WITH upsert AS materialized (
                            INSERT INTO recommendations (job_id, seeker_id, similarity_score)
                            SELECT job_id, $1 AS seeker_id, 1 - (embedding <=> $2::vector) AS similarity_score
                            FROM job_embedding
                            WHERE 1 - (embedding <=> $2::vector) > 0.55
                            ON CONFLICT (job_id, seeker_id) 
                            DO UPDATE SET similarity_score = EXCLUDED.similarity_score
                            RETURNING job_id
                        )
                        DELETE FROM recommendations
                        WHERE seeker_id = $1
                        AND not (job_id = any(SELECT job_id FROM upsert));
                    ''', user_id, f'{embedding}')
    print("Job recommendations updated for user:", user_id, flush=True)


async def recommend_users(job_id, embedding, conn):
    await conn.fetch('''with upsert as materialized (
                insert into recommendations (job_id, seeker_id, similarity_score)
                select $1 AS job_id, seeker_id, 1 - (embedding <=> $2::vector) AS similarity_score
                from job_seeker_embeddings
                where 1 - (embedding <=> $2::vector) > 0.55
                on conflict (job_id, seeker_id) do update set similarity_score = EXCLUDED.similarity_score
                returning seeker_id)
                delete from recommendations
                where job_id = $1
                and not(seeker_id = any (select seeker_id from upsert));''', job_id, f'{embedding}')
    