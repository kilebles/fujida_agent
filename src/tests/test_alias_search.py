def test_single_bliss_prefers_base(alias_service):
    res = alias_service.find_models("карма блис")
    assert res == ["Fujida Karma Bliss"]


def test_single_karma_prefers_base(alias_service):
    res = alias_service.find_models("карма")
    assert res == ["Fujida Karma"]


def test_single_pro_prefers_pro(alias_service):
    res = alias_service.find_models("карма про")
    assert res == ["Fujida Karma Pro"]


def test_pro_max_wifi(alias_service):
    res = alias_service.find_models("карма про макс вайфай")
    assert res
    assert res[0].startswith("Fujida Karma Pro Max")


def test_pro_max_rus_max(alias_service):
    res = alias_service.find_models("карма про макс")
    assert res
    assert res[0].startswith("Fujida Karma Pro Max")


def test_bliss_vs_pro_ordered_by_chunks(alias_service):
    res = alias_service.find_models("карма блис или карма про")
    assert res == ["Fujida Karma Bliss", "Fujida Karma Pro"]


def test_question_form_vs(alias_service):
    res = alias_service.find_models("что лучше карма про или карма блис?")
    assert res == ["Fujida Karma Pro", "Fujida Karma Bliss"]


def test_noise_long_text(alias_service):
    text = "Посоветуй пожалуйста, еду завтра, нужен видеорегистратор, думаю карма блис или все же карма про макс вайфай, что скажешь?"
    res = alias_service.find_models(text)
    assert res[0] in {"Fujida Karma Bliss", "Fujida Karma Pro Max Duo WiFi", "Fujida Karma Pro Max AI WiFi"}
    assert "Fujida Karma" not in res[:2]
