pipeline {
  agent any
  stages {
    stage('build') {
      steps {
        python setup.py sdist bdist_wheel
      }
    }
  }
}

