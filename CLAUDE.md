# CLAUDE.md - Guide for Agent Coding in Pyxis

## Build/Run/Test Commands
- Web server: `cd backend && pipenv run uvicorn app.main:app --reload`
- Format code: `cd backend && pipenv run black .`

## Code Style Guidelines
- **Imports**: Standard lib → Third-party → Project modules, with blank lines between groups
- **Formatting**: 4-space indentation, ~80-100 char line length, Black formatter
- **Naming**: snake_case for variables/functions, CamelCase for classes, ALL_CAPS for constants
- **Types**: Type hints for function parameters and return values (Python 3.10+ style)
- **Error Handling**: Use FastAPI HTTPException for API errors, include descriptive messages
- **Environment**: Use pipenv for dependency management
- **Documentation**: Docstrings with triple quotes, comments with # and space after

## Project Structure
- `/scripts_n_notebooks`: Data processing scripts, utilities and notebooks, do not modify code here.
- `/backend`: FastAPI web application
- `/docs`: Documentation and diagrams

# Background: Pyxis Project

Consistent estimation and monitoring of greenhouse gas (GHG) emissions in the Oil and Gas (O&G) industry faces significant challenges due to inaccessible, fragmented, and unstandardized datasets. Earlier efforts in estimating such emissions predominantly required extensive manual analysis to harmonize diverse data sources on O&G operations. Also, these analyses depend on crucial datasets such as flaring and methane leakage, which should ideally be updated in near real-time but are too large to integrate effectively. To tackle these challenges, this study proposes a Geographic Information System (GIS)-based data platform called Pyxis for integrating and managing data input associated with GHG emissions estimates in the O&G sector. The Pyxis architecture includes a scalable geodatabase for source management and an automated data pipeline for data management using spatial indexing, thereby reducing the manual labor traditionally needed for data matching and merging. In addition, top-down remote sensing data can be seamlessly associated with bottom-up field data through Pyxis, which improves data recency and spatiotemporal coverage. Here, we apply Pyxis to Brazil as a case study to show how it can help generate accurate estimates of Carbon Intensity (CI) with data management among disparate and inconsistent data sources. This work highlights the potential of scaling up Pyxis globally via integrating machine learning models for data extraction and ultimately becoming a valuable tool for GHG emissions monitoring and policymaking in the O&G industry.

# Tech Stack

Programming Language: Python 3.11, Javascript/TypeScript

Web Framework: FastAPI

Database: Postgres SQL

Postgres Extensions are listed as follows:

                                    List of installed extensions
      Name      | Version |   Schema   |                        Description
----------------+---------+------------+------------------------------------------------------------
 h3             | 4.1.3   | public     | H3 bindings for PostgreSQL
 h3_postgis     | 4.1.3   | public     | H3 PostGIS integration
 plpgsql        | 1.0     | pg_catalog | PL/pgSQL procedural language
 postgis        | 3.3.4   | public     | PostGIS geometry and geography spatial types and functions
 postgis_raster | 3.3.4   | public     | PostGIS raster types and functions

# Goal Overview

Implement a system called Pyxis proposed in a paper. High level tasks are listed:

1. Help me organize and refactor the existing python code for data processing(under the directory /db/data_processing and related files), try to use it later in web application building.
2. Use Docker to create a config for backend database(Postgres and extensions), so that the Pyxis project can be set up easily in different environment.
3. Design and build a geo database that complies with the requirements.
4. Build a web application to provide frontend UI and backend API for interacting with and querying the Pyxis geo database.

# Overall Instruction

1. Do not edit the files under db/. Only edit the web/ folder.

2. Lay out the changes you want to make and explain the thinking process before coding. Ask clarification questions when needed.

3. State what additional information you need and ask for my requirements if not given.

4. Build the project in an iterative approach. Break the project into reasonable small tasks. While developing, make sure the project is runnable after each steps.
