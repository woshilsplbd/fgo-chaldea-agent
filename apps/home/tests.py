from django.test import TestCase


class HomePageTests(TestCase):
    def test_homepage_uses_migrated_template_and_content(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/index.html")
        self.assertContains(response, "特异点观测记录")
