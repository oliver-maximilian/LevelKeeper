from levelkeeper.imap_client import _parse_list_line, decode_modified_utf7, folder_display_path


def test_decode_modified_utf7_plain_ascii():
    assert decode_modified_utf7("INBOX") == "INBOX"


def test_decode_modified_utf7_escaped_ampersand():
    assert decode_modified_utf7("Cars&-Bikes") == "Cars&Bikes"


def test_decode_modified_utf7_umlaut():
    assert decode_modified_utf7("Pers&APY-nlich") == "Persönlich"


def test_parse_list_line_quoted():
    line = b'(\\HasNoChildren) "/" "INBOX/Sent"'
    delim, name = _parse_list_line(line)
    assert delim == "/"
    assert name == "INBOX/Sent"


def test_parse_list_line_atom():
    line = b'(\\HasNoChildren) "." INBOX'
    delim, name = _parse_list_line(line)
    assert delim == "."
    assert name == "INBOX"


def test_folder_display_path_normalizes_delimiter():
    assert folder_display_path("INBOX.Projects.Foo", ".") == "INBOX/Projects/Foo"
