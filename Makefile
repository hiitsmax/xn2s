setup:
	uv sync --extra dev

run:
	uv run xs2n --help

test:
	uv run pytest

onboard-paste:
	uv run xs2n onboard --paste

onboard-following:
	@if [ -z "$(HANDLE)" ]; then \
		echo "Usage: make onboard-following HANDLE=your_screen_name"; \
		exit 1; \
	fi
	uv run xs2n onboard --from-following "$(HANDLE)"

wizard:
	uv run xs2n onboard --wizard
