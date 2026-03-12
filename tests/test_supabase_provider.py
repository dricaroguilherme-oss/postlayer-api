from __future__ import annotations

from app.infra.providers import supabase


def test_supabase_provider_strips_whitespace_from_env_settings() -> None:
    original_url = supabase.settings.supabase_url
    original_anon = supabase.settings.supabase_anon_key
    original_service = supabase.settings.supabase_service_role_key
    try:
        supabase.settings.supabase_url = "https://example.supabase.co \n"
        supabase.settings.supabase_anon_key = " anon-key \n"
        supabase.settings.supabase_service_role_key = " service-role \n"

        assert supabase.supabase_url() == "https://example.supabase.co"
        assert supabase.anon_key() == "anon-key"
        assert supabase.service_role_key() == "service-role"
    finally:
        supabase.settings.supabase_url = original_url
        supabase.settings.supabase_anon_key = original_anon
        supabase.settings.supabase_service_role_key = original_service
