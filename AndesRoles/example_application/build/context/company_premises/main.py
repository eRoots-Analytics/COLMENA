from example_application import CompanyPremises


if __name__ == '__main__':
	device = None # Environment variable, JSON file, TBD.
	r = CompanyPremises().locate(device)
