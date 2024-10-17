cd configuration
helm package . 
cp .\dwv-configuration-1.0.1-SNAPSHOT.tgz ..\datawave-monolith-umbrella\charts
cd ../datawave-monolith-umbrella
helm package .
cp .\datawave-monolith-umbrella-1.0.1-SNAPSHOT.tgz ..\datawave-stack\charts
cd ../datawave-stack
helm package .
helm template .\datawave-system-1.0.2-SNAPSHOT.tgz -f ..\my_values.yaml > tmp