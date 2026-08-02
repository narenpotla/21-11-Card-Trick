from django.urls import path

from . import views

app_name = "cardtrick"

urlpatterns = [
    path("", views.index, name="index"),
    path("start/", views.start_game, name="start_game"),
    path("choose/", views.choose_column, name="choose_column"),
    path("reset/", views.reset_game, name="reset_game"),
    path("learn/", views.learn_the_trick, name="learn"),
    path("why/", views.why_it_works, name="why"),
]
