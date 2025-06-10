import os
import json
import requests
from typing import Dict, List, Any
from flask import current_app

class AIService:
    """AI service for generating assessments and evaluating responses"""
    
    def __init__(self):
        self.groq_api_key = os.environ.get('GROQ_API_KEY', '')
        self.groq_base_url = 'https://api.groq.com/openai/v1'
        
        # Note: Logging will be done in methods that have app context
    
    def generate_assessment(self, job) -> Dict[str, Any]:
        """Generate AI-powered assessment for a job"""
        if not self.groq_api_key:
            try:
                current_app.logger.warning("GROQ_API_KEY not found - using fallback assessment")
            except RuntimeError:
                pass  # No app context available
            return self._get_fallback_assessment(job)
        
        try:
            # Prepare job context
            job_context = {
                'title': job.title,
                'description': job.description,
                'requirements': job.requirements,
                'responsibilities': job.responsibilities,
                'skills_required': job.get_skills_list(),
                'experience_level': job.experience_level,
                'employment_type': job.employment_type
            }
            
            # Generate questions using Groq API
            questions = self._generate_questions(job_context)
            projects = self._generate_projects(job_context)
            anti_cheat_rules = self._get_default_anti_cheat_rules()
            time_limit = self._calculate_time_limit(questions, projects)
            
            return {
                'questions': questions,
                'projects': projects,
                'anti_cheat_rules': anti_cheat_rules,
                'time_limit': time_limit
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating assessment with AI: {str(e)}")
            return self._get_fallback_assessment(job)
    
    def _generate_questions(self, job_context: Dict) -> List[Dict]:
        """Generate questions using Groq API"""
        prompt = self._build_questions_prompt(job_context)
        
        try:
            response = self._call_groq_api(prompt)
            
            # Parse the AI response
            questions_text = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            questions = self._parse_questions_response(questions_text, job_context)
            
            return questions
            
        except Exception as e:
            current_app.logger.error(f"Error generating questions: {str(e)}")
            return self._get_fallback_questions(job_context)
    
    def _generate_projects(self, job_context: Dict) -> List[Dict]:
        """Generate project assignments using Groq API"""
        prompt = self._build_projects_prompt(job_context)
        
        try:
            response = self._call_groq_api(prompt)
            
            # Parse the AI response
            projects_text = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            projects = self._parse_projects_response(projects_text, job_context)
            
            return projects
            
        except Exception as e:
            current_app.logger.error(f"Error generating projects: {str(e)}")
            return self._get_fallback_projects(job_context)
    
    def _call_groq_api(self, prompt: str) -> Dict:
        """Make API call to Groq"""
        headers = {
            'Authorization': f'Bearer {self.groq_api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'mixtral-8x7b-32768',
            'messages': [
                {'role': 'system', 'content': 'You are an expert technical recruiter and assessment creator. Generate high-quality, job-relevant questions and projects.'},
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': 2000,
            'temperature': 0.7
        }
        
        response = requests.post(
            f'{self.groq_base_url}/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        response.raise_for_status()
        return response.json()
    
    def _build_questions_prompt(self, job_context: Dict) -> str:
        """Build prompt for generating questions"""
        skills = ', '.join(job_context.get('skills_required', []))
        
        return f"""
        Create an assessment with 5-8 questions for this job position:
        
        Job Title: {job_context['title']}
        Experience Level: {job_context['experience_level']}
        Required Skills: {skills}
        
        Job Description: {job_context['description']}
        
        Generate a mix of:
        - 2-3 multiple choice questions (technical knowledge)
        - 2-3 short text answer questions (problem-solving)
        - 1-2 coding questions (if technical role)
        
        For each question, specify:
        1. Question type (multiple_choice, text, code)
        2. Question text
        3. Time limit in minutes (5-15 minutes per question)
        4. For multiple choice: 4 options and correct answer index
        5. Difficulty level (beginner, intermediate, advanced)
        
        Format as JSON with this structure:
        [
            {{
                "type": "multiple_choice",
                "question": "Question text here",
                "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
                "correct_answer": 0,
                "time_limit": 10,
                "difficulty": "intermediate"
            }}
        ]
        
        Make questions specific to the role and skills required.
        """
    
    def _build_projects_prompt(self, job_context: Dict) -> str:
        """Build prompt for generating project assignments"""
        skills = ', '.join(job_context.get('skills_required', []))
        
        return f"""
        Create 1-2 practical project assignments for this job position:
        
        Job Title: {job_context['title']}
        Required Skills: {skills}
        Experience Level: {job_context['experience_level']}
        
        Generate:
        1. One short-term project (2-4 hours, completed during assessment)
        2. One extended project (2-7 days, take-home assignment)
        
        For each project, specify:
        1. Project type (short or extended)
        2. Title
        3. Description and requirements
        4. Expected deliverables
        5. Time limit
        6. Evaluation criteria
        
        Format as JSON:
        [
            {{
                "type": "short",
                "title": "Project title",
                "description": "Detailed description",
                "requirements": "Specific requirements",
                "deliverables": "What to submit",
                "time_limit": 180,
                "evaluation_criteria": ["Criteria 1", "Criteria 2"]
            }}
        ]
        
        Make projects realistic and job-relevant.
        """
    
    def _parse_questions_response(self, response_text: str, job_context: Dict) -> List[Dict]:
        """Parse AI response for questions"""
        try:
            # Try to extract JSON from the response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                questions = json.loads(json_str)
                
                # Validate and enhance questions
                validated_questions = []
                for i, q in enumerate(questions):
                    if isinstance(q, dict) and 'question' in q and 'type' in q:
                        question = {
                            'id': i + 1,
                            'type': q.get('type', 'text'),
                            'question': q.get('question', ''),
                            'time_limit': min(max(q.get('time_limit', 10), 5), 30),
                            'difficulty': q.get('difficulty', 'intermediate'),
                            'rules': self._get_default_question_rules()
                        }
                        
                        if question['type'] == 'multiple_choice':
                            question['options'] = q.get('options', ['Option 1', 'Option 2', 'Option 3', 'Option 4'])
                            question['correct_answer'] = q.get('correct_answer', 0)
                        
                        validated_questions.append(question)
                
                if validated_questions:
                    return validated_questions
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            current_app.logger.error(f"Error parsing questions response: {str(e)}")
        
        return self._get_fallback_questions(job_context)
    
    def _parse_projects_response(self, response_text: str, job_context: Dict) -> List[Dict]:
        """Parse AI response for projects"""
        try:
            # Try to extract JSON from the response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                projects = json.loads(json_str)
                
                # Validate projects
                validated_projects = []
                for p in projects:
                    if isinstance(p, dict) and 'title' in p and 'type' in p:
                        project = {
                            'type': p.get('type', 'short'),
                            'title': p.get('title', ''),
                            'description': p.get('description', ''),
                            'requirements': p.get('requirements', ''),
                            'deliverables': p.get('deliverables', ''),
                            'evaluation_criteria': p.get('evaluation_criteria', [])
                        }
                        
                        if project['type'] == 'short':
                            project['time_limit'] = min(max(p.get('time_limit', 180), 60), 300)
                        else:
                            project['deadline_days'] = min(max(p.get('deadline_days', 7), 1), 14)
                        
                        validated_projects.append(project)
                
                if validated_projects:
                    return validated_projects
            
        except (json.JSONDecodeError, KeyError) as e:
            current_app.logger.error(f"Error parsing projects response: {str(e)}")
        
        return self._get_fallback_projects(job_context)
    
    def calculate_score(self, assessment, answers: Dict) -> float:
        """Calculate assessment score"""
        if not assessment or not answers:
            return 0.0
        
        questions = assessment.get_questions_list()
        if not questions:
            return 0.0
        
        total_questions = len(questions)
        correct_answers = 0
        
        for question in questions:
            question_id = f"question_{question['id']}"
            user_answer = answers.get(question_id)
            
            if question['type'] == 'multiple_choice':
                correct_index = question.get('correct_answer', 0)
                if user_answer is not None:
                    try:
                        if int(user_answer) == correct_index:
                            correct_answers += 1
                    except (ValueError, TypeError):
                        pass
            
            elif question['type'] in ['text', 'code']:
                # For text/code questions, we'll give partial credit if there's an answer
                # In a real implementation, you might use AI to evaluate these
                if user_answer and len(user_answer.strip()) > 10:
                    correct_answers += 0.7  # Partial credit
        
        return (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0
    
    def _get_fallback_assessment(self, job) -> Dict[str, Any]:
        """Get fallback assessment when AI is not available"""
        return {
            'questions': self._get_fallback_questions({'title': job.title, 'skills_required': job.get_skills_list()}),
            'projects': self._get_fallback_projects({'title': job.title}),
            'anti_cheat_rules': self._get_default_anti_cheat_rules(),
            'time_limit': 120
        }
    
    def _get_fallback_questions(self, job_context: Dict) -> List[Dict]:
        """Get fallback questions when AI generation fails"""
        job_title = job_context.get('title', 'Position')
        
        return [
            {
                'id': 1,
                'type': 'multiple_choice',
                'question': f'What interests you most about the {job_title} role?',
                'options': [
                    'The technical challenges and problem-solving opportunities',
                    'Working with a collaborative team environment',
                    'Learning new technologies and skills',
                    'Contributing to meaningful projects'
                ],
                'correct_answer': 0,
                'time_limit': 5,
                'difficulty': 'beginner',
                'rules': self._get_default_question_rules()
            },
            {
                'id': 2,
                'type': 'text',
                'question': f'Describe your relevant experience for this {job_title} position. What makes you a good fit?',
                'time_limit': 15,
                'difficulty': 'intermediate',
                'rules': self._get_default_question_rules()
            },
            {
                'id': 3,
                'type': 'text',
                'question': 'Describe a challenging problem you solved recently. What was your approach?',
                'time_limit': 10,
                'difficulty': 'intermediate',
                'rules': self._get_default_question_rules()
            }
        ]
    
    def _get_fallback_projects(self, job_context: Dict) -> List[Dict]:
        """Get fallback projects when AI generation fails"""
        job_title = job_context.get('title', 'Position')
        
        return [
            {
                'type': 'short',
                'title': f'{job_title} Case Study',
                'description': f'Complete a practical case study relevant to the {job_title} role.',
                'requirements': 'Analyze the given scenario and provide your recommendations.',
                'deliverables': 'Written analysis with your approach and recommendations.',
                'time_limit': 60,
                'evaluation_criteria': ['Problem analysis', 'Solution quality', 'Communication clarity']
            }
        ]
    
    def _get_default_anti_cheat_rules(self) -> Dict:
        """Get default anti-cheat rules"""
        return {
            'copy_paste_allowed': False,
            'tab_switching_allowed': False,
            'fullscreen_required': True,
            'webcam_required': True,
            'right_click_disabled': True,
            'inspect_disabled': True,
            'screenshot_disabled': True,
            'max_violations': 3,
            'violation_warning': True
        }
    
    def _get_default_question_rules(self) -> Dict:
        """Get default rules for individual questions"""
        return {
            'copy_paste_allowed': False,
            'tab_switching_allowed': False,
            'webcam_required': True,
            'fullscreen_required': True
        }
    
    def _calculate_time_limit(self, questions: List, projects: List) -> int:
        """Calculate total time limit for assessment"""
        total_time = 0
        
        # Add time for questions
        for question in questions:
            total_time += question.get('time_limit', 10)
        
        # Add time for short projects
        for project in projects:
            if project.get('type') == 'short':
                total_time += project.get('time_limit', 60)
        
        # Add buffer time (20%)
        total_time = int(total_time * 1.2)
        
        # Ensure minimum and maximum limits
        return min(max(total_time, 30), 300)  # 30 min to 5 hours
