# BSC COLMENA Project

## Introduction  

The **BSC COLMENA Project** focuses on developing a use case for **COLMENA** in the domain of electrical grid control and operation. **COLMENA** (*COLaboración entre dispositivos Mediante tecnología de ENjAmbre*) is a framework designed to facilitate the development, deployment, operation, and maintenance of highly available, reliable, and intelligent services across the **device-edge-cloud continuum**. It employs a **swarm-based approach**, where autonomous and collaborative nodes operate in a fully decentralized, secure, and trustworthy architecture.  

This project aims to **demonstrate the applicability of COLMENA** in power system operations by leveraging its decentralized control paradigm to enhance grid stability, resilience, and efficiency. By integrating **COLMENA’s swarm intelligence**, we explore how distributed coordination can improve real-time decision-making and adaptability in electrical grids. The results of this project will validate COLMENA’s potential in critical infrastructure applications and provide insights into its real-world deployment.  

## Requirements  

To use this project, you need **COLMENA**, which is available at:  

-🔗 [COLMENA GitHub Repository](https://github.com/colmena-swarm)  

Ensure that **COLMENA and its dependencies** are installed before running the use case.

You also need **Docker** for containerized execution:  

- 🔗 [Docker Website](https://www.docker.com/)  
- 🔗 [Docker Installation Guide](https://docs.docker.com/get-docker/)  

## Repository Structure  

### **AndesApp Folder**  
The **AndesApp** folder contains essential files for the use case, including:  

- A **customized Andes version** with **new models and routines** for the use case.  
- An **implementation of Andes in Flask**, enabling integration realtime simulation of a grid in parallel with COLMENA integration.  
- A **stable version** of the customized Andes setup for testing and deployment.  

### **AndesRoles Folder**  



## **Usage & First Testing**  
To launch the Flask implementation of Andes, run:  
```bash
python AndesApp/Scripts/app_andes_interfacy.py
```

#### **Running a Stable Dynamic Grid Case**  
To execute a stable version of a dynamic grid simulation (IEEE 39-bus case), run:  

```bash
python AndesApp/Scripts/ieee39_cases/ieee39_REDUAL.py
```

This simulation provides a desired scenario in which a grid changes dynamically through the simulation. The charge of different loads as well as the operation mode of different converters change during the simulation. 

#### **Service & Role definition**  

Service Definition and Role definition can be found the file:

```bash
AndesRoles/Scripts/example_eroots_edit.py
```

For testing purposes, these roles can be executed alongside AndesApp in Flask by running the script.
```bash
python AndesRoles/main.py
```

Changing the line to the appropriate file name and service name changes the executed roles. 

```python
from eroots_test import ErootsUseCase
from ${FileName} import ${ServiceName}
```
Executing the roles in this way runs the roles continuously disregarding the activation condition for the role (KPIs). For a complete COLMENA execution run the following file (Not fully supported):

```bash
python AndesApp/colmena_deploy/colmena_terminals.py
```

Before running the code it is important to also change your machine's local IP in the service definition to ensure the program is working as intended. 

```python
# Update this to match your machine's local IP before running the script
HOST_IP = "192.168.1.122"
```
Then you can chose which service to run by changing the line:

```python
SERVICE_FILENAME = 'eroots_test'
```

This will launch a simulation of colmena with 2 different agents in different docker containers.
