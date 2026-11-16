from datetime import date

import pandas as pd
import pytest

from scripts.evaluate import discover_answers, evaluate, filtered_cert, label, ranking_metrics, read_answers


def test_metrics_use_test_rows_and_distinct_positive_users():
    frame = pd.DataFrame([
        {"user_id": "A", "date": date(2026, 1, 1), "positive": True, "score": 10},
        {"user_id": "A", "date": date(2026, 1, 2), "positive": True, "score": 9},
        {"user_id": "B", "date": date(2026, 1, 1), "positive": False, "score": 8},
    ])
    result = ranking_metrics(frame, "score")
    assert result["p10"] == pytest.approx(2 / 3)
    assert result["users10"] == 1
    assert result["top5"] == 1
    assert result["recall5"] == .5


def test_answers_intervals_and_seeded_sampling(tmp_path):
    answers_dir = tmp_path / "answers"
    answers_dir.mkdir()
    answer_file = answers_dir / "insider.csv"
    answer_file.write_text("user_id,start_date,end_date\nI,01/01/2010,01/03/2010\n", encoding="utf-8")
    answers, invalid = read_answers(discover_answers(tmp_path))
    assert invalid == 0
    assert label("I", date(2010, 1, 2), answers)
    assert not label("I", date(2010, 1, 4), answers)
    events = tmp_path / "logon.csv"
    events.write_text("date,user,pc,activity\n" +
                      "".join(f"01/01/2010 09:00:00,U{i:03},PC,Logon\n" for i in range(220)) +
                      "01/02/2010 09:00:00,I,PC,Logon\n", encoding="utf-8")
    first, population, selected = filtered_cert([events], answers, tmp_path / "first")
    second, _, _ = filtered_cert([events], answers, tmp_path / "second")
    assert (population, selected) == (221, 201)
    assert first[0].read_bytes() == second[0].read_bytes()
    assert ",I," in first[0].read_text()


def test_small_cert_end_to_end(tmp_path):
    cert = tmp_path / "cert"
    cert.mkdir()
    (cert / "logon.csv").write_text(
        "id,date,user,pc,activity\n" +
        "".join(f"{d},01/0{d}/2010 09:00:00,A,PC,Logon\n" for d in range(1, 5)) +
        "".join(f"{d+4},01/0{d}/2010 09:00:00,B,PC,Logon\n" for d in range(1, 5)),
        encoding="utf-8",
    )
    answer = tmp_path / "labels.csv"
    answer.write_text("user,start,end\nA,01/04/2010,01/04/2010\n", encoding="utf-8")
    output = evaluate(cert, answer)
    assert output.startswith("Dataset: CERT;")
    assert "Test labels: 1 positive user-days across 1 insiders." in output
    assert "Rankings: P@10" in output
    assert "99.9 | 99 |" in output


def test_cert_without_labels_fails_clearly(tmp_path):
    (tmp_path / "logon.csv").write_text("date,user,pc,activity\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no answers"):
        evaluate(tmp_path)
