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

### **andes** 
This folder contains a modified version of the power system dynamic simulator ANDES. In particular, the modes of the governors used in the three cases kundur, ieee39 and npcc have been changed such that the distributed MPC scheme do not need to be modified depending on the considered case.

### **notebooks** 
This folder contains contains notebooks to play around with ANDES and learn about all of its functionalities and peculiarities. 

### **plots** 
This folder is used to save all result figures.

### **scripts**
This folder contains the main script, which intializes the web communication between coordinator and ANDES, run the simulation and plot the results. 

### **src**
This folder contains the following: 
- config: where all the system parameters are defined and stored.
- controller: where the DMPC is implemented
    - mpc_agent.py defines the agent optimization problem 
    - admm.py performs the admm algorithm, i.e. first it solves for each agent, then it check for convergence and finally it executes the duals and parameters update if necessary. 
    - coordinator.py coordinates the simulation with the execution of the DMPC and manage the sharing of variables. 
- simulator: where the web interface with ANDES is defined
    - andes_api.py defines all the web application functions using Flask that allow the coordinator to communicate with ANDES via POST/GET requests. 
    - andes_wrapper.py wraps all these functions for readibility porpuses. 

### **tests** 
This folder contains test scripts.

### **utils** 
This folder contains util functions.
- plotting.py is where all the plots are defined. 

#### **Running a Stable Dynamic Grid Case**  
To execute a stable version of a dynamic grid simulation (kundur, ieee39 or npcc), run:  

```bash
python scripts/main.py
```

This simulation provides a desired scenario in which a grid changes dynamically through the simulation. To change the case to simulate it is necessary to change the config.py file. 

