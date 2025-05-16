from typing import List, Dict, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class ChatbotScorer:
    def __init__(self, client, embedding):
        """
        Initialize the ChatbotScorer with an LLM evaluator and sentence transformer.
        The LLM evaluator should be a callable that takes a prompt and returns a response.
        """
        self.client = client
        # Initialize sentence transformer for computing embeddings
        self.sentence_transformer = embedding

    def _compute_cosine_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts using sentence transformers.
        """
        # Get embeddings
        embedding1 = self.sentence_transformer.encode([text1])[0]
        embedding2 = self.sentence_transformer.encode([text2])[0]
        
        # Reshape embeddings for cosine_similarity
        embedding1 = embedding1.reshape(1, -1)
        embedding2 = embedding2.reshape(1, -1)
        
        # Compute cosine similarity
        similarity = cosine_similarity(embedding1, embedding2)[0][0]
        return float(similarity)
    def llm(self, prompt):
        response = self.client.chat.completions.create(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    def score_faithfulness(self, answer: str, context: str, question: str) -> float:
        """
        Calculate faithfulness score through a three-step process:
        1. Generate claims from the answer using LLM with examples
        2. Verify each claim against the context with detailed reasoning
        3. Calculate ratio of supported claims to total claims
        
        Args:
            answer: The generated answer to evaluate
            context: The context used to generate the answer
            question: The original question asked
            
        Returns:
            float: Score between 0 and 1 representing faithfulness
        """
        # Step 1: Generate claims from the answer using example-based prompt
        claims_prompt = f"""You are a smart AI.Take the questions and their answers and make one or more statements from each sentence in the given answers.
Use the following examples to understand how to make statements from the answers:
###Example 1:
Question: Who is Albert Einstein and what is he best known for?
Answer: He was a German-born theoretical physicist who is widely regarded as one of the greatest and most influential physicists of all time. He is best known for developing the theory of relativity and also made important contributions to the development of the theory of quantum mechanics.
Claim:
Albert Einstein was born in Germany.
Albert Einstein is best known for his theory of relativity.
###Example 2:
Question: Cadmium chloride is slightly soluble in this chemical, what is it also called?
Answer: Alcohol
Claim:
Cadmium chloride is slightly soluble in alcohol.
###Example 3:
Question: Are Shahul and Jitin of the same nationality?
Answer: They are from different countries.
Claim:
Shahul and Jitin are from different countries.
Based on the above examples, make statements from the following answer strictly following the examples.:
Question:{question}
Answer:{answer}
Claim:"""

        try:
            # Get claims from LLM
            claims_response = self.llm(claims_prompt)
            print("\nClaim_response",claims_response)
            # Parse claims (assuming they're separated by newlines)
            claims = [claim.strip() for claim in claims_response.split('\n') 
                     if claim.strip() and not claim.startswith('Question:') and not claim.startswith('Answer:')]
            
            if not claims:
                return 0.0
                
            # Step 2: Verify each claim against the context with detailed reasoning
            verification_prompt = f"""Prompt: Natural Language Inference
Consider the given context and the statements below and determine whether they are supported by the information present in the context. Provide a brief explanation for each statement before coming to a conclusion (yes/no). Provide a final conclusion for each statement in the specified format. Do not deviate from the specified format.

Context:
John is a student at XYZ University. He is pursuing a degree in Computer Science. He is enrolled in several courses this semester including Data Structures, Algorithms, and Database Management. John is a hardworking student and spends a significant amount of time studying and completing assignments. He often works on projects late into the night in the library.
Assertion:
1. John is majoring in Biology.
2. John is taking a course in Artificial Intelligence.
3. John is a dedicated student.
4. John has a part-time job.
5. John is interested in computer programming.
Answer:
1. John is majoring in Biology.
Explanation: John's major is explicitly stated as Computer Science. There is no information that he is majoring in Biology. Conclusion: No.
2. John is taking a course in artificial intelligence.

Explanation: The context mentions the course in which John is currently enrolled, and no mention is made of artificial intelligence. Therefore, it cannot be inferred that John is taking a course in AI. Conclusion: No.

3. John is a dedicated student.

Explanation: The prompt states that he spends a significant amount of time studying and completing assignments. Furthermore, it is also stated that he often stays up late working on projects in the library, which suggests that he is dedicated. Conclusion: Yes.

4. John has a part-time job.

Explanation: The context does not provide any information that John has a part-time job. Therefore, it cannot be inferred that John has a part-time job. Conclusion: No.

5. John is interested in computer programming.

Explanation: The context states that John has a degree in computer science, which suggests an interest in computer programming. Conclusion: Yes.

Final conclusion (in order): No. No. Yes. No. Yes.

Context: {context}
Assertion: {claims}
Answer:"""
            
            # Get verification from LLM
            verification = self.llm(verification_prompt)
            
            # Parse the final conclusion line to count supported claims
            try:
                final_line = [line for line in verification.split('\n') if 'Final conclusion' in line][0]
                conclusions = final_line.split(':')[1].strip().split('.')
                supported_claims = sum(1 for c in conclusions if c.strip().upper() == 'YES')
                total_claims = len([c for c in conclusions if c.strip().upper() in ['YES', 'NO']])
                
                if total_claims == 0:
                    return 0.0
                    
                return supported_claims / total_claims
                
            except Exception as e:
                print(f"Error parsing verification response: {str(e)}")
                return 0.0
            
        except Exception as e:
            print(f"Error calculating faithfulness score: {str(e)}")
            return 0.0

    def score_answer_relevancy(self, answer: str, question: str) -> float:
        """
        Calculate answer relevancy through question reconstruction and similarity:
        1. Reconstruct a question from the answer using example-based prompt
        2. Calculate cosine similarity between original and reconstructed question
        
        Args:
            answer: The generated answer to evaluate
            question: The original question
            
        Returns:
            float: Score between 0 and 1 representing answer relevancy
        """
        # Step 1: Generate question from the answer using example
        question_reconstruction_prompt = f"""Generate questions for the given answers.
Answer:
The PSLV-C56 mission is scheduled to launch on Sunday, July 30, 2023 at 06:30 IST/01:00 UTC. It will launch from Satish Dhawan Space Centre, Sriharikota, Andhra Pradesh, India.
Question: What is the scheduled launch date, time and launch location for the PSLV-C56 mission?

Answer:{answer}
Question:"""

        try:
            # Get reconstructed question from LLM
            reconstructed_question = self.llm(question_reconstruction_prompt).strip()
            
            if not reconstructed_question:
                return 0.0
            
            # Step 2: Calculate cosine similarity between original and reconstructed question
            similarity = self._compute_cosine_similarity(question, reconstructed_question)
            
            return float(similarity)
            
        except Exception as e:
            print(f"Error calculating answer relevancy score: {str(e)}")
            return 0.0

    def score_context_recall(self, context: str, ground_truth: str) -> float:
        """
        Evaluate how well the retrieved context covers the ground truth.
        Returns a score between 0 and 1.
        """
        prompt = f"""Evaluate how much of the ground truth information is covered by the given context.
Consider:
1. What key information from the ground truth appears in the context?
2. What important details are missing?

Context: {context}
Ground Truth: {ground_truth}

Coverage score (0-1):"""
        
        try:
            score = float(self.llm(prompt))
            return max(0.0, min(1.0, score))
        except:
            return 0.0

    def score_context_precision(self, contexts: List[str], question: str) -> float:
        """
        Evaluate how precise and relevant the retrieved contexts are to the question.
        Returns a score between 0 and 1.
        """
        if not contexts:
            return 0.0

        scores = []
        for ctx in contexts:
            prompt = f"""Rate how relevant this context piece is to answering the question.
Consider:
1. Does it contain information needed to answer the question?
2. How much irrelevant information does it contain?

Question: {question}
Context: {ctx}

Relevance score (0-1):"""
            
            try:
                score = float(self.llm(prompt))
                scores.append(max(0.0, min(1.0, score)))
            except:
                scores.append(0.0)

        return np.mean(scores) if scores else 0.0

    def _parse_faithfulness_evaluation(self, evaluation: str) -> List[Dict[str, str]]:
        """
        Parse the LLM's faithfulness evaluation into structured data.
        This is a placeholder - implement based on your LLM's output format.
        """
        # Implement parsing logic based on your LLM's output format
        # Should return a list of dicts with keys: 'statement', 'reason', 'Attributed'
        return []

    def evaluate_response(self, 
                         question: str,
                         answer: str,
                         context: str,
                         ground_truth: str = None,
                         contexts: List[str] = None) -> Dict[str, float]:
        """
        Evaluate a chatbot response using all available metrics.
        Returns a dictionary of scores.
        """
        scores = {
            'faithfulness': self.score_faithfulness(answer, context, question),
            'answer_relevancy': self.score_answer_relevancy(answer, question),
        }
        
        if ground_truth:
            scores['context_recall'] = self.score_context_recall(context, ground_truth)
            
        if contexts:
            scores['context_precision'] = self.score_context_precision(contexts, question)
            
        return scores 