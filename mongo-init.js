// MongoDB initialization script to create additional admin users
// This script runs when the MongoDB container is first initialized

db = db.getSiblingDB('admin');

// Create a second admin user
db.createUser({
  user: 'admin2',
  pwd: 'admin2_password',
  roles: [
    {
      role: 'root',
      db: 'admin'
    }
  ]
});

print('Additional admin user created successfully');

