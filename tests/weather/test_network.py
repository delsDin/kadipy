import pytest
from kadi._utils.network import fetch_with_retry
from kadi.exceptions import DataSourceError

def test_fetch_with_retry_success():
    """Test le succès immédiat sans réessais."""
    def mock_fetch(x):
        return x * 2
        
    result = fetch_with_retry(mock_fetch, attempts=3, backoff_sec=0, x=5)
    assert result == 10

def test_fetch_with_retry_fails_then_succeeds():
    """Test un échec initial suivi d'un succès."""
    attempts_tracker = {"count": 0}
    
    def mock_fetch():
        attempts_tracker["count"] += 1
        if attempts_tracker["count"] < 3:
            raise ValueError("Erreur réseau temporaire")
        return "Succès"
        
    result = fetch_with_retry(mock_fetch, attempts=3, backoff_sec=0)
    assert result == "Succès"
    assert attempts_tracker["count"] == 3

def test_fetch_with_retry_all_fail():
    """Test l'épuisement de toutes les tentatives."""
    def mock_fetch():
        raise ValueError("Serveur KO")
        
    with pytest.raises(DataSourceError):
        fetch_with_retry(mock_fetch, attempts=2, backoff_sec=0)
