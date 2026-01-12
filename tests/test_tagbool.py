import pickle
from dap_db_manager.tagging.titleformat.tagbool import TagBool, TagTrue, TagFalse


class TestTagBool:
    """Tests for TagBool and related classes."""

    def test_pickle_tagbool_true(self):
        """Test pickling TagBool(True)."""
        obj = TagBool(True, "1")
        pickled = pickle.dumps(obj)
        unpickled = pickle.loads(pickled)
        assert unpickled == "1"
        assert bool(unpickled) is True
        assert type(unpickled) is type(obj)

    def test_pickle_tagbool_false(self):
        """Test pickling TagBool(False)."""
        obj = TagBool(False, "")
        pickled = pickle.dumps(obj)
        unpickled = pickle.loads(pickled)
        assert unpickled == ""
        assert bool(unpickled) is False
        assert type(unpickled) is type(obj)

    def test_pickle_tagtrue(self):
        """Test pickling TagTrue."""
        obj = TagTrue()
        pickled = pickle.dumps(obj)
        unpickled = pickle.loads(pickled)
        assert unpickled == "1"
        assert bool(unpickled) is True

    def test_pickle_tagfalse(self):
        """Test pickling TagFalse."""
        obj = TagFalse()
        pickled = pickle.dumps(obj)
        unpickled = pickle.loads(pickled)
        assert unpickled == ""
        assert bool(unpickled) is False

    def test_concatenation(self):
        """Test addition behavior of TagBool objects."""
        t1 = TagTrue("A")
        t2 = TagTrue("B")
        res = t1 + t2
        assert res == "AB"
        assert bool(res) is True

        f1 = TagFalse("C")
        f2 = TagFalse("D")
        res = f1 + f2
        assert res == "CD"
        assert bool(res) is False

        res = t1 + f1
        assert res == "AC"
        assert bool(res) is True

    def test_repr(self):
        """Test string representation."""
        t = TagTrue("val")
        assert repr(t) == "TagTrue('val')"

        f = TagFalse("val")
        assert repr(f) == "TagFalse('val')"
