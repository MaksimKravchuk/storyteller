"""Tests for engine.graph_populator.

Exercises each branch of populate_graph_from_setting so we catch regressions in
the Setting→KnowledgeGraph seeding path used by the engine factory.
"""

from __future__ import annotations

import allure

from engine.graph_populator import populate_graph_from_setting
from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, KnowledgeScope, KnowledgeSource
from models.setting import Setting


def _nodes_by_scope(graph: KnowledgeGraph, scope: KnowledgeScope):
    return [node for node in graph.all_nodes() if node.scope == scope]


def _texts(nodes) -> list[str]:
    return [node.text for node in nodes]


@allure.epic("Game World")
@allure.feature("Knowledge graph population")
class TestPopulateGraphFromSetting:
    @allure.story("Setting summary")
    @allure.title("Setting summary is added as a WORLD-scope FACT node tagged setting/overview")
    def test_summary_added_as_world_node(self):
        graph = KnowledgeGraph()
        setting = Setting(name="Rome", time_period="1 AD", region="Italy", summary="Eternal city")

        populate_graph_from_setting(graph, setting)

        world_nodes = _nodes_by_scope(graph, KnowledgeScope.WORLD)
        assert len(world_nodes) == 1
        assert world_nodes[0].text == "Eternal city"
        assert world_nodes[0].source == KnowledgeSource.FACT
        assert "setting" in world_nodes[0].tags
        assert "overview" in world_nodes[0].tags

    @allure.story("Key persons")
    @allure.title("Each key person becomes a COUNTRY-scope node with education gating and person/politics tags")
    def test_key_persons_added_as_country_nodes(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="",
            key_persons=[
                {"name": "Caesar", "role": "dictator", "description": "Crossed the Rubicon"},
                {"name": "Cicero", "role": "orator", "description": "Famous speaker"},
            ],
        )

        populate_graph_from_setting(graph, setting)

        country_nodes = _nodes_by_scope(graph, KnowledgeScope.COUNTRY)
        person_texts = _texts(country_nodes)
        assert any("Caesar: dictator. Crossed the Rubicon" in text for text in person_texts)
        assert any("Cicero: orator. Famous speaker" in text for text in person_texts)
        for node in country_nodes:
            if node.text.startswith(("Caesar", "Cicero")):
                assert node.required_education == 3
                assert "person" in node.tags
                assert "politics" in node.tags

    @allure.story("Key persons")
    @allure.title("Person entries missing optional fields fall back to 'Unknown' and empty strings")
    def test_key_person_with_missing_fields_uses_defaults(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="X",
            time_period="y",
            region="z",
            summary="",
            key_persons=[{}],
        )

        populate_graph_from_setting(graph, setting)

        country_nodes = _nodes_by_scope(graph, KnowledgeScope.COUNTRY)
        assert any(node.text.startswith("Unknown:") for node in country_nodes)

    @allure.story("Key events")
    @allure.title("Key events become REGION-scope nodes tagged event/history with education=2")
    def test_key_events_added_as_region_nodes(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="",
            key_events=[{"name": "Crossing the Rubicon", "date": "49 BC", "description": "Caesar crosses"}],
        )

        populate_graph_from_setting(graph, setting)

        region_nodes = _nodes_by_scope(graph, KnowledgeScope.REGION)
        event_nodes = [node for node in region_nodes if "event" in node.tags]
        assert len(event_nodes) == 1
        assert "Crossing the Rubicon (49 BC): Caesar crosses" == event_nodes[0].text
        assert event_nodes[0].required_education == 2
        assert "history" in event_nodes[0].tags

    @allure.story("Key events")
    @allure.title("Event entries missing name fall back to 'Unknown event'")
    def test_event_with_missing_name_uses_default(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="X",
            time_period="y",
            region="z",
            summary="",
            key_events=[{}],
        )

        populate_graph_from_setting(graph, setting)

        assert any("Unknown event" in node.text for node in graph.all_nodes())

    @allure.story("Locations")
    @allure.title("Setting.locations entries become CITY-scope nodes tagged 'location'")
    def test_locations_added_as_city_nodes(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="",
            locations=[{"name": "Forum", "type": "square", "description": "Political center"}],
        )

        populate_graph_from_setting(graph, setting)

        city_nodes = _nodes_by_scope(graph, KnowledgeScope.CITY)
        assert len(city_nodes) == 1
        assert city_nodes[0].text == "Forum (square): Political center"
        assert "location" in city_nodes[0].tags

    @allure.story("Locations")
    @allure.title("Location entries missing name fall back to 'Unknown place'")
    def test_location_with_missing_name_uses_default(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="X",
            time_period="y",
            region="z",
            summary="",
            locations=[{}],
        )

        populate_graph_from_setting(graph, setting)

        assert any("Unknown place" in node.text for node in graph.all_nodes())

    @allure.story("Traditions")
    @allure.title("Each tradition becomes a REGION-scope node tagged tradition/culture")
    def test_traditions_added_as_region_nodes(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="",
            traditions=["toga", "bathing"],
        )

        populate_graph_from_setting(graph, setting)

        region_nodes = _nodes_by_scope(graph, KnowledgeScope.REGION)
        tradition_nodes = [node for node in region_nodes if "tradition" in node.tags]
        assert _texts(tradition_nodes) == ["toga", "bathing"]
        for node in tradition_nodes:
            assert "culture" in node.tags

    @allure.story("Technologies")
    @allure.title("Technologies become REGION-scope nodes with education=1 and tech tags")
    def test_technologies_added_with_education_gating(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="",
            technologies=["aqueducts"],
        )

        populate_graph_from_setting(graph, setting)

        region_nodes = _nodes_by_scope(graph, KnowledgeScope.REGION)
        tech_nodes = [node for node in region_nodes if "technology" in node.tags]
        assert len(tech_nodes) == 1
        assert tech_nodes[0].text == "aqueducts"
        assert tech_nodes[0].required_education == 1

    @allure.story("Social structure")
    @allure.title("social_structure string is added as a COUNTRY-scope node with education=2")
    def test_social_structure_added_when_nonempty(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="",
            social_structure="patrician/plebeian",
        )

        populate_graph_from_setting(graph, setting)

        country_nodes = _nodes_by_scope(graph, KnowledgeScope.COUNTRY)
        social_nodes = [node for node in country_nodes if "society" in node.tags]
        assert len(social_nodes) == 1
        assert social_nodes[0].text == "patrician/plebeian"
        assert social_nodes[0].required_education == 2
        assert "social_structure" in social_nodes[0].tags

    @allure.story("Social structure")
    @allure.title("Empty social_structure string is not added as a node")
    def test_empty_social_structure_omitted(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="",
            social_structure="",
        )

        populate_graph_from_setting(graph, setting)

        assert all("society" not in node.tags for node in graph.all_nodes())

    @allure.story("Full populate")
    @allure.title("A richly-populated Setting adds one node per entry plus the overview — totals match")
    def test_total_node_count_across_all_categories(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="Eternal city",
            key_persons=[{"name": "Caesar"}, {"name": "Cicero"}],
            key_events=[{"name": "Rubicon"}],
            locations=[{"name": "Forum"}, {"name": "Colosseum"}],
            traditions=["toga"],
            technologies=["aqueducts"],
            social_structure="republic",
        )

        populate_graph_from_setting(graph, setting)

        # 1 summary + 2 persons + 1 event + 2 locations + 1 tradition + 1 tech + 1 social = 9
        assert len(graph.all_nodes()) == 9

    @allure.story("Canon source")
    @allure.title("Every node produced by populate_graph_from_setting is marked as HISTORICAL canon")
    def test_all_populated_nodes_are_historical_canon(self):
        graph = KnowledgeGraph()
        setting = Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="Eternal city",
            key_persons=[{"name": "Caesar"}],
            key_events=[{"name": "Rubicon"}],
            locations=[{"name": "Forum"}],
            traditions=["toga"],
            technologies=["aqueducts"],
            social_structure="republic",
        )

        populate_graph_from_setting(graph, setting)

        for node in graph.all_nodes():
            assert node.canon == CanonSource.HISTORICAL
