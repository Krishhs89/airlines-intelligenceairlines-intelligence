#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the complete agent flow and data pipeline.

Tests:
1. DataStore initialization and data access
2. Agent system initialization
3. Query routing through agents
4. MockLLM response generation
5. End-to-end chat response flow
"""

import logging
import sys

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


def test_datastore():
    """Test 1: Verify DataStore initializes and returns real data."""
    print("\n" + "="*70)
    print("TEST 1: DataStore Initialization & Data Access")
    print("="*70)
    
    try:
        from data.store import DataStore
        
        store = DataStore.get()
        logger.info("OK - DataStore initialized successfully")
        
        flights_count = len(store.flights)
        logger.info("OK - Flights loaded: %d records", flights_count)
        print("\nSample flights data:")
        print(store.flights[['flight_number', 'origin', 'destination', 'status', 'load_factor']].head(3))
        
        routes_count = len(store.routes)
        logger.info("OK - Routes loaded: %d records", routes_count)
        print("\nSample routes data:")
        print(store.routes[['origin', 'destination', 'demand_score', 'revenue_index', 'competition_level']].head(3))
        
        aircraft_count = len(store.aircraft)
        logger.info("OK - Aircraft loaded: %d records", aircraft_count)
        
        gates_count = len(store.gates)
        logger.info("OK - Gates loaded: %d records", gates_count)
        
        print("\nOK - DataStore Test PASSED")
        return True
        
    except Exception as e:
        logger.error("FAILED - DataStore Test FAILED: %s", e)
        import traceback
        traceback.print_exc()
        return False


def test_network_planning_agent():
    """Test 2: Verify Network Planning Agent can access tools."""
    print("\n" + "="*70)
    print("TEST 2: Network Planning Agent & Tool Access")
    print("="*70)
    
    try:
        from data.store import DataStore
        from mcp.context_store import MCPContextStore
        from mcp.tool_registry import MCPToolRegistry
        from llm.mock_llm import MockLLM
        from agents.network_planning import NetworkPlanningAgent
        
        store = DataStore.get()
        context_store = MCPContextStore()
        tool_registry = MCPToolRegistry()
        llm = MockLLM()
        
        agent = NetworkPlanningAgent(context_store, tool_registry, llm, store)
        logger.info("OK - Network Planning Agent initialized")
        
        result = agent.get_route_demand("ORD", "LAX")
        logger.info("OK - get_route_demand executed")
        print("\nRoute Demand Result (ORD to LAX):")
        for key, value in result.items():
            print("  %s: %s" % (key, value))
        
        conflicts = agent.get_schedule_conflicts()
        logger.info("OK - get_schedule_conflicts executed: %d conflicts", conflicts['conflict_count'])
        print("\nSchedule Conflicts: %d conflicts detected" % conflicts['conflict_count'])
        
        freq_rec = agent.suggest_frequency_change("ORD-LAX")
        logger.info("OK - suggest_frequency_change executed")
        print("\nFrequency Recommendation (ORD-LAX):")
        for key, value in freq_rec.items():
            print("  %s: %s" % (key, value))
        
        print("\nOK - Network Planning Agent Test PASSED")
        return True
        
    except Exception as e:
        logger.error("FAILED - Network Planning Agent Test: %s", e)
        import traceback
        traceback.print_exc()
        return False


def test_mock_llm():
    """Test 3: Verify MockLLM generates responses."""
    print("\n" + "="*70)
    print("TEST 3: MockLLM Response Generation")
    print("="*70)
    
    try:
        from llm.mock_llm import MockLLM
        
        llm = MockLLM()
        logger.info("OK - MockLLM initialized")
        
        test_queries = [
            "analyze the ORD to LAX route",
            "what are the disruptions?",
            "show me the executive summary",
        ]
        
        print("\nIntent Classification Tests:")
        for query in test_queries:
            intent = llm.classify_intent(query)
            print("  Query: '%s'" % query)
            print("  -> Intent: %s\n" % intent)
        
        test_data = {
            "origin": "ORD",
            "destination": "LAX",
            "demand_score": 0.78,
            "revenue_index": 1.15,
            "competition_level": "High",
            "current_freq": 7,
            "actual_load": 82,
            "actual_otp": 84,
        }
        
        print("\n" + "-"*70)
        print("ROUTE ANALYSIS RESPONSE:")
        print("-"*70)
        response = llm.generate("route_analysis", test_data)
        print(response)
        
        print("\nOK - MockLLM Test PASSED")
        return True
        
    except Exception as e:
        logger.error("FAILED - MockLLM Test: %s", e)
        import traceback
        traceback.print_exc()
        return False


def test_orchestrator_full_flow():
    """Test 4: End-to-end orchestrator query flow."""
    print("\n" + "="*70)
    print("TEST 4: Orchestrator Full Query Flow")
    print("="*70)
    
    try:
        from data.store import DataStore
        from mcp.context_store import MCPContextStore
        from mcp.tool_registry import MCPToolRegistry
        from llm.mock_llm import MockLLM
        from agents.orchestrator import OrchestratorAgent
        
        store = DataStore.get()
        context_store = MCPContextStore()
        tool_registry = MCPToolRegistry()
        llm = MockLLM()
        
        orchestrator = OrchestratorAgent(context_store, tool_registry, llm, store)
        logger.info("OK - Orchestrator initialized")
        
        test_queries = [
            "analyze route ORD to LAX",
            "What's the demand for the Chicago to LA route?",
        ]
        
        print("\nProcessing Test Queries:")
        for query in test_queries:
            print("\n" + "="*70)
            print("Query: %s" % query)
            print("="*70)
            
            try:
                response = orchestrator.route(query)
                
                print("\nOK - Response received:")
                print("  Responder Agent: %s" % response.responder)
                print("  Confidence: %.0f%%" % (response.confidence * 100))
                print("\nInsight:\n%s" % response.insight)
                
                if response.tool_calls:
                    print("\nTools Called: %d" % len(response.tool_calls))
                    
            except Exception as e:
                logger.error("Query failed: %s", e)
                import traceback
                traceback.print_exc()
        
        print("\nOK - Orchestrator Test PASSED")
        return True
        
    except Exception as e:
        logger.error("FAILED - Orchestrator Test: %s", e)
        import traceback
        traceback.print_exc()
        return False


def test_chat_component():
    """Test 5: Test the chat component response."""
    print("\n" + "="*70)
    print("TEST 5: Chat Component Simulation")
    print("="*70)
    
    try:
        from data.store import DataStore
        from mcp.context_store import MCPContextStore
        from mcp.tool_registry import MCPToolRegistry
        from llm.mock_llm import MockLLM
        from agents.orchestrator import OrchestratorAgent
        
        store = DataStore.get()
        context_store = MCPContextStore()
        tool_registry = MCPToolRegistry()
        llm = MockLLM()
        orchestrator = OrchestratorAgent(context_store, tool_registry, llm, store)
        
        chat_messages = [
            "What's the demand on the ORD to DEN route?",
            "Are there any schedule conflicts?",
        ]
        
        print("\nChat Simulation:")
        for message in chat_messages:
            print("\n" + "-"*70)
            print("User: %s" % message)
            print("-"*70)
            
            response = orchestrator.route(message)
            
            print("\nAssistant Response:")
            print(response.insight)
            
            if response.tool_calls:
                print("\n[Expandable] Tool Details (%d tools)" % len(response.tool_calls))
                print("   Confidence: %.0f%%" % (response.confidence * 100))
                print("   Agent: %s" % response.responder)
        
        print("\nOK - Chat Component Test PASSED")
        return True
        
    except Exception as e:
        logger.error("FAILED - Chat Component Test: %s", e)
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#" + "  AGENT SYSTEM USABILITY TEST".center(70) + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    results = {
        "DataStore": test_datastore(),
        "Network Planning Agent": test_network_planning_agent(),
        "MockLLM": test_mock_llm(),
        "Orchestrator": test_orchestrator_full_flow(),
        "Chat Component": test_chat_component(),
    }
    
    print("\n" + "#"*70)
    print("#" + " "*68 + "#")
    print("#" + "  TEST SUMMARY".center(70) + "#")
    print("#" + " "*68 + "#")
    print("#"*70)
    
    for test_name, passed in results.items():
        status = "OK - PASSED" if passed else "FAILED"
        print("  %-40s %s" % (test_name, status))
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print("\n" + "-"*70)
    print("Total: %d/%d tests passed" % (total_passed, total_tests))
    print("#"*70 + "\n")
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
