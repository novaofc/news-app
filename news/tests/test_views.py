"""Website view tests: access control for the editor workflow and
subscriptions."""

from django.core import mail
from django.urls import reverse

from news.models import Article

from .base import NewsTestCase


class EditorReviewViewTests(NewsTestCase):
    def test_editor_sees_review_queue(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse("news:review_queue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending story")

    def test_journalist_cannot_open_review_queue(self):
        self.client.force_login(self.journalist)
        response = self.client.get(reverse("news:review_queue"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse("news:review_queue"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_editor_approves_through_website(self):
        self.client.force_login(self.editor)
        url = reverse("news:approve_article", args=[self.pending_article.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse("news:review_queue"))
        self.pending_article.refresh_from_db()
        self.assertTrue(self.pending_article.approved)
        self.assertEqual(self.pending_article.approved_by, self.editor)
        self.assertEqual(len(mail.outbox), 1)
        self.mock_post.assert_called_once()

    def test_approve_requires_post(self):
        self.client.force_login(self.editor)
        url = reverse("news:approve_article", args=[self.pending_article.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_reader_cannot_approve_through_website(self):
        self.client.force_login(self.reader)
        url = reverse("news:approve_article", args=[self.pending_article.pk])
        self.assertEqual(self.client.post(url).status_code, 403)


class ArticleViewTests(NewsTestCase):
    def test_home_lists_only_approved_articles(self):
        response = self.client.get(reverse("news:home"))
        self.assertContains(response, "Publisher story")
        self.assertNotContains(response, "Pending story")

    def test_reader_cannot_open_unapproved_article(self):
        self.client.force_login(self.reader)
        url = reverse("news:article_detail", args=[self.pending_article.pk])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_journalist_creates_article(self):
        self.client.force_login(self.indie)
        response = self.client.post(
            reverse("news:article_create"),
            {"title": "Web article", "content": "Body", "publisher": ""},
        )
        article = Article.objects.get(title="Web article")
        self.assertRedirects(response, article.get_absolute_url())
        self.assertEqual(article.author, self.indie)
        self.assertFalse(article.approved)

    def test_reader_cannot_create_article(self):
        self.client.force_login(self.reader)
        response = self.client.get(reverse("news:article_create"))
        self.assertEqual(response.status_code, 403)

    def test_journalist_cannot_edit_others_article(self):
        self.client.force_login(self.indie)
        url = reverse(
            "news:article_update", args=[self.publisher_article.pk]
        )
        self.assertEqual(self.client.get(url).status_code, 403)


class SubscriptionViewTests(NewsTestCase):
    def test_reader_can_subscribe_and_unsubscribe(self):
        self.client.force_login(self.reader)
        url = reverse(
            "news:toggle_subscription", args=["journalist", self.indie.pk]
        )
        self.client.post(url)
        self.assertIn(self.indie, self.reader.subscribed_journalists.all())
        self.client.post(url)
        self.assertNotIn(
            self.indie, self.reader.subscribed_journalists.all()
        )

    def test_journalist_cannot_subscribe(self):
        self.client.force_login(self.journalist)
        url = reverse(
            "news:toggle_subscription", args=["publisher", self.publisher.pk]
        )
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_signup_assigns_role_and_group(self):
        response = self.client.post(
            reverse("news:signup"),
            {
                "username": "newbie",
                "email": "newbie@example.com",
                "role": "journalist",
                "password1": "Sup3r-Secret-Pass",
                "password2": "Sup3r-Secret-Pass",
            },
        )
        self.assertRedirects(response, reverse("news:home"))
        from news.models import CustomUser
        user = CustomUser.objects.get(username="newbie")
        self.assertTrue(user.is_journalist)
        self.assertTrue(user.groups.filter(name="Journalist").exists())

    def test_signup_cannot_choose_editor_role(self):
        response = self.client.post(
            reverse("news:signup"),
            {
                "username": "sneaky",
                "email": "sneaky@example.com",
                "role": "editor",
                "password1": "Sup3r-Secret-Pass",
                "password2": "Sup3r-Secret-Pass",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
