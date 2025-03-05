# Collaboration guide.

!!! IMPORTANT !!!
Do not rush to code before asking for my permission. Always lay out the steps you plan to take first. Stop generating after finish each step and discuss the result with me before proceeding to the next step. Development plan should be broken into small tasks and after each step, we should be able to test the system.

Always state clearly these:

1. What is going to be implmented. Purpose and functionality.
2. The file locations.

# Coding guide.

1. Do not duplicate enum definitions, define it once and use it everywhere.
2. Only expose model classes instead of enums in __init__.py file under models/ folder to avoid possible circular dependencies. The purpose is to let sqlalchemy know what data we have.

