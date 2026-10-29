import unittest

from app.llm import study_prompt, study_teacher_system


class StudyPromptTests(unittest.TestCase):
    def test_subject_and_exam_modes_are_specific(self):
        prompt = study_prompt("Make a set", "[1] (notes.txt)\nVectors", "maths", "jee")
        self.assertIn("SUBJECT: maths", prompt)
        self.assertIn("JEE-style", prompt)
        self.assertIn("not verified past JEE questions", prompt)
        self.assertIn("Vectors", prompt)

    def test_prompt_does_not_claim_generated_past_questions(self):
        system = study_teacher_system("biology", "XII")
        prompt = study_prompt("Important questions", "(no relevant excerpts were found)", "biology", "important_questions")
        self.assertIn("Do not claim a generated question appeared", system)
        self.assertIn("never call them actual previous-year questions", prompt)

    def test_lesson_and_check_modes_wait_for_the_learners_answer(self):
        lesson = study_prompt("Teach this chapter", "", "physics", "lesson", "Laws of motion")
        check = study_prompt("Ask me a question", "", "physics", "check", "Laws of motion")
        system = study_teacher_system("physics", "XI")

        self.assertIn("selected topic is 'Laws of motion'", lesson)
        self.assertIn("exactly one short question", lesson)
        self.assertIn("wait for the learner", lesson)
        self.assertIn("exactly one short", check)
        self.assertIn("Do not reveal the answer", check)
        self.assertIn("When the learner answers your check question", system)


if __name__ == "__main__":
    unittest.main()
