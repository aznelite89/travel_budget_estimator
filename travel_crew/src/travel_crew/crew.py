from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from crewai_tools import SerperDevTool
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class TravelCrew():
    """TravelCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def trip_planner(self) -> Agent:
        return Agent(
            config=self.agents_config['trip_planner'], # type: ignore[index]
            verbose=True
        )

    @agent
    def flight_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['flight_agent'],
            verbose=True,
            tools=[SerperDevTool()]
        )
    
    @agent
    def stay_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['stay_agent'], # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool()]
        )

    @agent
    def transport_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['transport_agent'], # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool()]
        )

    @agent
    def food_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['food_agent'], # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool()]
        )
    
    @agent
    def activity_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['activity_agent'], # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool()]
        )
    
    @agent
    def docs_fees_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['docs_fees_agent'], # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool()]
        )
    
    @agent
    def risk_buffer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['risk_buffer_agent'], # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool()]
        )
    
    @agent
    def budget_aggregator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['budget_aggregator_agent'], # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool()]
        )
    
    @agent
    def validator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['validator_agent'], # type: ignore[index]
            verbose=True,
            tools=[SerperDevTool()]
        )
    
    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def validate_trip_info(self) -> Task:
        return Task(
            config=self.tasks_config['validate_trip_info'], # type: ignore[index]
        )

    @task
    def produce_trip_plan(self) -> Task:
        return Task(
            config=self.tasks_config['produce_trip_plan'], # type: ignore[index]
            output_file='report.md'
        )
    
    @task
    def validate_flight_info(self) -> Task:
        return Task(
            config=self.tasks_config['validate_flight_info'], # type: ignore[index]
        )
    
    @task
    def produce_flight_plan(self) -> Task:
        return Task(
            config=self.tasks_config['produce_flight_plan'], # type: ignore[index]
            output_file='flight_plan.md'
        )






    @crew
    def crew(self) -> Crew:
        """Creates the TravelCrew crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
