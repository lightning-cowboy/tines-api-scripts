# Tines API Scripts
* Original development goal was to export all relevant Tines application data to GitHub for version control
* * However this was abandoned due to technical limitations
* Now, what we have is a set of scripts for getting data out of or into a Tines tenant
* We can use **tines_get** for quick exports of data such as events as the data from the API is more verbose than from the UI
* Another use case is using **tines_compare** to "diff" the contents of one tenant with another
* * This was successfully used for migrating from a Cloud Tenant to our current Self-Hosted solution
