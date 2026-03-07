// Jenkinsfile — Pipeline CI/CD: Build → Test → Deploy-Test → Approve → Deploy-Prod
// Best Practice: Declarative Pipeline con agent Kubernetes, credentials store, timeout
 
pipeline {

agent {
    kubernetes {
        yaml '''
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins
  containers:
  - name: docker
    image: docker:24-dind
    securityContext:
      privileged: true
    env:
    - name: DOCKER_TLS_CERTDIR
      value: ""
    - name: DOCKER_HOST
      value: tcp://localhost:2375
  - name: kubectl
    image: alpine/k8s:1.29.2
    command: ["cat"]
    tty: true
        '''
    }
}

    environment {
        REGISTRY     = 'docker.io'
        IMAGE_NAME   = 'zecko8/myapp'
        IMAGE_TAG    = sh(script: 'git rev-parse --short=8 HEAD', returnStdout: true).trim()
        FULL_IMAGE   = "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
        REGISTRY_CREDS = credentials('registry-credentials')
    }

    options {
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    parameters {
        booleanParam(
            name: 'SKIP_TESTS',
            defaultValue: false,
            description: 'Salta i test unitari (solo per debug)'
        )
        choice(
            name: 'PROD_REPLICAS',
            choices: ['2', '3', '5'],
            description: 'Numero di repliche in produzione'
        )
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                sh 'echo "Branch: ${GIT_BRANCH} | Commit: ${IMAGE_TAG}"'
            }
        }

        stage('Build Image') {
            steps {
                container('docker') {
                    sh '''
                        echo "=== Attesa daemon Docker ==="
                        until docker -H tcp://localhost:2375 info > /dev/null 2>&1; do
                            echo "Docker non ancora pronto, attendo..."
                            sleep 2
                        done
                        echo "Docker pronto"
                        echo "=== Build immagine ${FULL_IMAGE} ==="
                        docker -H tcp://localhost:2375 build \
                            --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
                            --build-arg VERSION=${IMAGE_TAG} \
                            -t ${FULL_IMAGE} .
                    '''
                }
            }
        }

        stage('Push Image') {
            steps {
                container('docker') {
                    sh '''
                        echo "=== Push immagine nel registry ==="
                        echo ${REGISTRY_CREDS_PSW} | \
                            docker -H tcp://localhost:2375 login ${REGISTRY} -u ${REGISTRY_CREDS_USR} --password-stdin
                        docker -H tcp://localhost:2375 push ${FULL_IMAGE}
                        docker -H tcp://localhost:2375 tag ${FULL_IMAGE} ${IMAGE_NAME}:latest
                        docker -H tcp://localhost:2375 push ${IMAGE_NAME}:latest
                    '''
                }
            }
        }

        stage('Deploy in TEST') {
            steps {
                container('kubectl') {
                    sh '''
                        echo "=== Deploy in namespace TEST (${IMAGE_TAG}) ==="
                        sed -i "s|REGISTRY/myapp:IMAGE_TAG|${FULL_IMAGE}|g" k8s/deployment-test.yaml
                        sed -i "s|IMAGE_TAG|${IMAGE_TAG}|g" k8s/deployment-test.yaml

                        kubectl apply -f k8s/deployment-test.yaml
                        kubectl apply -f k8s/service-test.yaml

                        echo "Attesa rollout completamento..."
                        kubectl rollout status deployment/myapp -n test --timeout=5m
                    '''
                }
            }
        }

        stage('Smoke Test (TEST)') {
            steps {
                container('kubectl') {
                    sh '''
                        echo "=== Smoke test namespace test ==="
                        kubectl wait pod -l app=myapp -n test --for=condition=Ready --timeout=2m
        
                        POD=$(kubectl get pod -l app=myapp -n test \
                              --sort-by=.metadata.creationTimestamp \
                              -o jsonpath='{.items[-1].metadata.name}')
        
                        echo "Pod selezionato: $POD"
                        HTTP_CODE=$(kubectl exec $POD -n test -- \
                                    curl -s -o /dev/null -w "%{http_code}" \
                                    http://localhost:8080/health)
        
                        if [ "$HTTP_CODE" != "200" ]; then
                            echo "SMOKE TEST FALLITO: HTTP $HTTP_CODE"
                            exit 1
                        fi
                        echo "Smoke test SUPERATO (HTTP 200)"
                    '''
                }
            }
        }

        stage('Approvazione Deploy PROD') {
            steps {
                echo "Deploy in TEST completato. In attesa di approvazione per PROD..."
                timeout(time: 30, unit: 'MINUTES') {
                    input message: 'Approvare il deploy in PRODUZIONE?',
                          ok: "Si', approvo il deploy",
                          parameters: [
                              string(name: 'CHANGE_TICKET',
                                     description: 'Numero ticket di change (es. JIRA-1234)',
                                     defaultValue: '')
                          ]
                }
            }
        }

        stage('Deploy in PROD') {
            steps {
                container('kubectl') {
                    sh '''
                        echo "=== Deploy in namespace PROD (${IMAGE_TAG}) ==="
                        sed -i "s|REGISTRY/myapp:IMAGE_TAG|${FULL_IMAGE}|g" k8s/deployment-prod.yaml
                        sed -i "s|IMAGE_TAG|${IMAGE_TAG}|g" k8s/deployment-prod.yaml
                        sed -i "s|replicas: 2|replicas: ${PROD_REPLICAS}|g" k8s/deployment-prod.yaml

                        kubectl apply -f k8s/deployment-prod.yaml
                        kubectl apply -f k8s/service-prod.yaml

                        echo "Attesa rollout PROD..."
                        kubectl rollout status deployment/myapp -n prod --timeout=10m

                        echo "=== DEPLOY PROD COMPLETATO ==="
                        kubectl get pods -n prod
                    '''
                }
            }
        }

        stage('Verifica PROD') {
            steps {
                container('kubectl') {
                    sh '''
                        echo "=== Verifica finale PROD ==="
                        kubectl get deployment myapp -n prod
                        kubectl get pods -n prod -l app=myapp
                        kubectl describe deployment myapp -n prod | grep -E "Image:|Replicas:|Available"
                    '''
                }
            }
        }
    }

    post {
        success {
            echo "Pipeline COMPLETATA con successo!"
            echo "Immagine deployata: ${FULL_IMAGE}"
        }
        failure {
            echo "Pipeline FALLITA"
        }
        aborted {
            echo "Deploy in PROD annullato dall'operatore"
        }
        always {
            echo "Fine pipeline"
        }
    }
}
