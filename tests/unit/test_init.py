from vigilant import main


def test_main_prints_greeting(capsys) -> None:
    main()

    captured = capsys.readouterr()

    assert captured.out == "Hello from vigilant!\n"
