import ollama
import pdfplumber
import numpy as np
from datetime import datetime
from groq import Groq
from groq import AsyncGroq
import os
import re
import json
import io
from minio import Minio
import psycopg2
import asyncpg
import asyncio
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

download_path = "./"
pool = None 
client_minio = Minio(endpoint= "localhost:9000",
    access_key= "minio",
    secret_key= "miniopass",
    secure=False)
client = AsyncGroq(

    api_key= "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",

)

model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

async def run():
    # Establish a connection to the database
    global pool
    pool = await asyncpg.create_pool(host = "localhost", database="app", user="app_user", password="public1",port="5432",min_size=15,max_size=20)

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
        await run()
    async with pool.acquire() as conn:
        if type == 'cv':

            rows = await conn.fetch("SELECT skills FROM CV_Keywords WHERE cv_id = $1", id)
            skills = rows[0][0]
            response = client_minio.get_object("cvs-bucket", f"{id}.pdf")
            pdf_bytes = io.BytesIO(response.read())

            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    print(text)
            
            weight_cv = '''You are an expert in analyzing candidate CVs to assess skill proficiency. Given a CV and a list of extracted skills, evaluate the candidate’s experience in each skill and assign a rating from 1 (poor) to 5 (excellent) based on:
            - Years of experience
            - Projects or work history related to the skill
            - Certifications, courses, or achievements

            Return the result in the following **JSON format**:

            {
            "skills": {
                "Skill 1": rate,
                "Skill 2": rate
            }
            }

            **Rules:**
            - If the candidate has **no mention** of experience for a skill, rate it **1**.
            - If the skill is mentioned **briefly** or in a general context, rate it **2-3**.
            - If the candidate has **mid experience, projects**, rate it **4**.
            - If the candidate has **strong experience, projects, or certifications**, rate it **5**.
            - Write the JSON format without 'JSON' in the beginning.

            **Example Input:**
            ---
            CV:
            "I have been working as a Data Scientist for 5 years, primarily using Python and TensorFlow for Machine Learning. I also have experience with SQL databases and AWS cloud services. Recently, I completed a certification in NLP."

            Extracted Skills:
            ["Python", "Machine Learning", "SQL", "AWS", "NLP", "Deep Learning"]

            **Expected Output:**
            ---
            {
            "skills": {
                "Python": 5,
                "Machine Learning": 5,
                "SQL": 4,
                "AWS": 4,
                "NLP": 5,
                "Deep Learning": 2
            }
            }

            Now, analyze the following CV and extracted skills and return the JSON response.

            CV: \n''' + text + '''\n \n Extracted Skills: \n''' + f'''{skills}'''

            CV_weight_query = await client.chat.completions.create(

                messages=[

                    {

                        "role": "user",

                        "content": weight_cv,

                    }

                ],

                model="llama-3.3-70b-versatile",

            )

            CV_weight = CV_weight_query.choices[0].message.content

            skills_dict_cv = json.loads(CV_weight)

            weighted_cv_embedding = get_embeddings(skills_dict_cv['skills'])

            await conn.fetch("insert into cv_embedding(cv_id,vector) values ($1,$2) on conflict (cv_id) do nothing;",id,f'{weighted_cv_embedding.tolist()}')

        elif type == 'job':
            rows = await conn.fetch('''select json_object_agg(skills.name,job_skill.importance) 
                        from job_skill 
                        join skills on job_skill.skill_id = skills.id
                        where job_skill.job_id = $1''',id)
            skills = json.loads(rows[0][0])
            weighted_job_embedding = get_embeddings(skills)
            await recommend_users(id, weighted_job_embedding.tolist(), conn)
            await conn.fetch("insert into job_embedding(job_id,embedding) values ($1,$2) on conflict (job_id) do nothing;",id,f'{weighted_job_embedding.tolist()}')

        if type == 'profile' or type == 'cv':
            cv_id = None

            
            rows = await conn.fetch('''select array_agg(json_build_object(
                        "school_name",education.school_name,
                        "field", education.field, 
                        "degree",education.degree,
                        "grade",education.grade))
                        from education
                        where education.user_id =$1''',user_id)
            education = rows[0][0]

            
            
            rows = await conn.fetch('''select array_agg(json_build_object(
                        "company_name",user_experience.company_name,
                        "start_date",user_experience.start_date,
                        "end_date",user_experience.end_date,
                        "description",user_experience.description,
                        "job_title",user_experience.job_title))
                        from user_experience
                        where user_experience.user_id = $1''',user_id)
            experience = rows[0][0]

            

            rows = await conn.fetch('''select array_agg(skills.name)
                        from user_skills
                        join skills on user_skills.skill_id = skills.id
                        where user_skills.user_id = $1''',user_id)
            skills = rows[0][0]

            if type == 'cv':
                cv_id = id
            else:
                
                rows = await conn.fetch('''select id
                            from CV
                            where user_id = $1 and deleted = false and created_at = (select max(created_at) from (select created_at from cv where user_id= $1))
                            ''',user_id)
                cv_id = rows[0][0]

            cv = client_minio.get_object("cvs-bucket", f"{cv_id}.pdf")

            pdf_bytes = io.BytesIO(cv.read())

            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    cv_text = page.extract_text()
            

            weight_profile = '''You are an expert in analyzing candidate CVs to assess skill proficiency. Given a CV, a list of extracted skills, Education as an array of dictionaries, and
            Experiences as an array of dictionaries, evaluate the candidate’s experience in each skill and assign a rating from 1 (poor) to 5 (excellent) based on:
            - Years of experience
            - Projects or work history related to the skill
            - Certifications, courses, or achievements

            Return the result in the following **JSON format**:

            {
            "skills": {
                "Skill 1": rate,
                "Skill 2": rate
            }
            }

            **Rules:**
            - If the candidate has **no mention** of experience for a skill, rate it **1**.
            - If the skill is mentioned **briefly** or in a general context, rate it **2-3**.
            - If the candidate has **mid experience, projects**, rate it **4**.
            - If the candidate has **strong experience, projects, and certifications**, rate it **5**.
            - Write the JSON format without 'JSON' in the beginning.
            - Look up the candidate's projects from the CV.
            - Look up the experience and education from both CV and the given list.
            - If the same experience/education is present in the CV and the list, consider only the one in the CV.
            - The output should be the JSON format only.

            **Example Input:**
            ---
            CV:
            "Assiut University, Faculty of Computers and Information, Egypt Aug 18 – Aug 22
            Bachelor's degree in bioinformatics.Overall Grade: 3.48 out of 4.0.
            I have worked as a Data Scientist at Microsoft for 5 years, primarily using Python and TensorFlow for Machine Learning. I also have experience with SQL databases and AWS cloud services. Recently, I completed a certification in NLP."

            Extracted Skills:
            ["Python", "Machine Learning", "SQL", "AWS", "NLP", "Deep Learning"]

            Extracted Experience:
            [{"company_name": "Microsoft",
            "start_date": "2020",
            "end_date": "2025",
            "description": "I have been working as a Data Scientist in Microsoft for 5 years, primarily using Python and TensorFlow for Machine Learning.",
            "job_title": "Data Scientist"}]

            Extracted Education:
            [{"school_name": "Assiut University",
            "field": "Faculty of Computers and Information",
            "degree": "Bachelor's degree in bioinformatics",
            "grade": "3.48"}]

            **Expected Output:**
            ---
            {
            "skills": {
                "Python": 5,
                "Machine Learning": 5,
                "SQL": 4,
                "AWS": 4,
                "NLP": 5,
                "Deep Learning": 2
            }
            }

            Now, analyze the following CV and extracted skills and return the JSON response.

            CV: \n''' + cv_text + '''\n \n Extracted Skills: \n''' + f'''{skills}''' + '''\n \n Extracted Experience: \n''' + f'''{experience}''' + '''\n \n Extracted Education: \n''' + f'''{education}'''

            profile_weight_query = await client.chat.completions.create(

                messages=[

                    {

                        "role": "user",

                        "content": weight_profile,

                    }

                ],

                model="llama-3.3-70b-versatile",

            )
            profile_weight = profile_weight_query.choices[0].message.content

            skills_dict_profile = json.loads(profile_weight)

            weighted_profile_embedding = get_embeddings(skills_dict_profile['skills'])

            await recommend_jobs(user_id, weighted_profile_embedding.tolist(),conn)
            await conn.fetch('''insert into job_seeker_embeddings(seeker_id,embedding) values ($1,$2) 
                            on conflict (seeker_id) do update set embedding = excluded.embedding;''',user_id,f'{weighted_profile_embedding.tolist()}')


async def recommend_jobs(user_id, embedding, conn):
    await conn.fetch('''WITH upsert AS materialized (
                            INSERT INTO recommendations (job_id, seeker_id, similarity_score)
                            SELECT job_id, $1 AS seeker_id, 1 - (embedding <=> $2::vector) AS similarity_score
                            FROM job_embedding
                            WHERE 1 - (embedding <=> $2::vector) > 0.1
                            ON CONFLICT (job_id, seeker_id) 
                            DO UPDATE SET similarity_score = EXCLUDED.similarity_score
                            RETURNING job_id
                        )
                        DELETE FROM recommendations
                        WHERE seeker_id = $1
                        AND not (job_id = any(SELECT job_id FROM upsert));
                    ''', user_id, f'{embedding}')


async def recommend_users(job_id, embedding, conn):
    await conn.fetch('''with upsert as materialized (
                insert into recommendations (job_id, seeker_id, similarity_score)
                select $1 AS job_id, seeker_id, 1 - (embedding <=> $2::vector) AS similarity_score
                from job_seeker_embeddings
                where 1 - (embedding <=> $2::vector) > 0.1
                on conflict (job_id, seeker_id) do update set similarity_score = EXCLUDED.similarity_score
                returning seeker_id)
                delete from recommendations
                where job_id = $1
                and not(seeker_id = any (select seeker_id from upsert));''', job_id, f'{embedding}')
    

asyncio.run(main_function(1,3,'job'))





