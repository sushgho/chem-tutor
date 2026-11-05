import unittest

from app.llm import study_prompt, study_teacher_system


class StudyPromptTests(unittest.TestCase):
    def test_math_answers_use_renderable_latex_and_plain_language_explanations(self):
        for subject in ("maths", "physics", "chemistry", "biology"):
            with self.subTest(subject=subject):
                system = study_teacher_system(subject, "XI")
                self.assertIn("inline LaTeX delimiters $...$", system)
                self.assertIn("plain-language explanation", system)
                self.assertIn("Avoid unnatural phrasing", system)

    def test_chemistry_teacher_uses_readable_structure_and_explains_equations(self):
        from app.llm import teacher_system

        system = teacher_system("XI")
        self.assertIn("direct answer", system)
        self.assertIn("a few clear bullets", system)
        self.assertIn("explain it immediately in plain language", system)
        self.assertIn("Do not write awkward prose", system)

    def test_math_validation_rules_apply_to_all_subjects_and_chemistry(self):
        from app.llm import teacher_system

        systems = [
            study_teacher_system(subject, "XI")
            for subject in ("maths", "physics", "chemistry", "biology")
        ] + [teacher_system("XI")]
        for system in systems:
            with self.subTest(system=system[:40]):
                self.assertIn("show the solution step by step", system)
                self.assertIn("fraction_simplifier tool", system)
                self.assertRegex(system.lower(), r"fraction.*(?:reduc|simplif)|(?:reduc|simplif).*fraction")
                self.assertIn("between 0 and 1 inclusive", system)
                self.assertIn("boxed mathematical format", system)
                self.assertIn("distinguish intermediate calculations from the final answer", system)
                self.assertIn("verify that the simplified fraction is equivalent", system)
                self.assertIn("Final Answer:", system)

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

    def test_all_subjects_get_guidance_for_useful_rendered_diagrams(self):
        for subject in ("maths", "physics", "chemistry", "biology"):
            with self.subTest(subject=subject):
                system = study_teacher_system(subject, "XI")
                self.assertIn("Mermaid flowchart or concept map", system)
                self.assertIn("```mermaid", system)
                self.assertIn("instead of an ASCII-art diagram", system)
                self.assertIn("original textbook page preview", system)
                self.assertIn("Do not force a diagram", system)


if __name__ == "__main__":
    unittest.main()
