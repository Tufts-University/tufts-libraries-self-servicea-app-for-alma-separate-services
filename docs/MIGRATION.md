# Migration checks

1. Keep the current production/stage application checkout intact.
2. Remove only the first-generation generated systemd units with `scripts/remove_first_generation.sh`.
3. Import source into this repository.
4. Run `grep -R "from app\\.\\|import app\\." services` and resolve any remaining references.
5. Run `scripts/validate_structure.py`.
6. Copy current environment variables into `/etc/self-service-app/self-service.env`.
7. Install/start the new `self-service.target`.
8. Verify `curl http://127.0.0.1:5002/health/services`.
9. Test every public route through the existing Apache URL.
10. Only then retire the original monolith.
