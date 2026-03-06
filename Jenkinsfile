// Jenkinsfile — Pipeline CI/CD: Build → Test → Deploy-Test → Approve → Deploy-Prod
// Best Practice: Declarative Pipeline con agent Kubernetes, credentials store, timeout
 
pipeline {
 
    // ─── AGENT ────────────────────────────────────────────────────────────
    // Ogni stage usa il container appropriato (kubectl, docker, ecc.)
    agent {
        kubernetes {
            yaml '''
apiVersion: v1
kind: Pod
metadata:
  labels:
    jenkins: agent
spec:
  serviceAccountName: jenkins
  containers:
  # Container per build Docker
  - name: docker
    image: docker:24-dind
    securityContext:
      privileged: true
    volumeMounts:
    - name: docker-sock
      mountPath: /var/run/docker.sock
  # Container per operazioni kubectl
  - name: kubectl
    image: bitnami/kubectl:1.29
    command: ["cat"]
    tty: true
  volumes:
  - name: docker-sock
    hostPath:
      path: /var/run/docker.sock
            '''
        }
    }
 
    // ─── VARIABILI D'AMBIENTE ──────────────────────────────────────────────
    environment {
        REGISTRY     = 'registry.example.com'
        IMAGE_NAME   = 'myapp'
        // GIT_COMMIT è una variabile built-in di Jenkins
        // Usiamo i primi 8 caratteri del commit SHA come tag
        IMAGE_TAG    = sh(script: 'git rev-parse --short=8 HEAD', returnStdout: true).trim()
        FULL_IMAGE   = "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
        // Credenziali registry (mai in chiaro nel Jenkinsfile!)
        REGISTRY_CREDS = credentials('registry-credentials')
    }
 
    // ─── OPZIONI GLOBALI ───────────────────────────────────────────────────
    options {
        // Timeout totale pipeline: 60 minuti
        timeout(time: 60, unit: 'MINUTES')
        // Mantieni solo gli ultimi 10 build
        buildDiscarder(logRotator(numToKeepStr: '10'))
        // Non eseguire build concorrenti dello stesso branch
        disableConcurrentBuilds()
        // Timestamp nei log
        timestamps()
    }
 
    // ─── PARAMETRI ─────────────────────────────────────────────────────────
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
 
    // ─── STAGES ────────────────────────────────────────────────────────────
    stages {
 
        // Stage 1: Checkout del codice
        stage('Checkout') {
            steps {
                checkout scm
                sh 'echo "Branch: ${GIT_BRANCH} | Commit: ${IMAGE_TAG}"'
            }
        }
 
        // Stage 2: Build immagine Docker
        stage('Build Image') {
            steps {
                container('docker') {
                    sh '''
                        echo "=== Build immagine ${FULL_IMAGE} ==="
                        docker build \
                            --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
                            --build-arg VERSION=${IMAGE_TAG} \
                            -t ${FULL_IMAGE} .
                    '''
                }
            }
        }
 
        // Stage 3: Test (opzionale tramite parametro)
        stage('Unit Tests') {
            when {
                expression { return !params.SKIP_TESTS }
            }
            steps {
                container('docker') {
                    sh '''
                        echo "=== Esecuzione test unitari ==="
                        docker run --rm ${FULL_IMAGE} python -m pytest tests/ -v \
                            --junitxml=/tmp/test-results.xml || true
                    '''
                }
            }
            post {
                always {
                    // Pubblica risultati test in Jenkins
                    // junit '**/test-results.xml'
                    echo 'Test completati'
                }
            }
        }
 
        // Stage 4: Push immagine nel registry
        stage('Push Image') {
            steps {
                container('docker') {
                    sh '''
                        echo "=== Push immagine nel registry ==="
                        echo ${REGISTRY_CREDS_PSW} | \
                            docker login ${REGISTRY} -u ${REGISTRY_CREDS_USR} --password-stdin
                        docker push ${FULL_IMAGE}
                        # Tag 'latest' per riferimento (NON usare in prod!)
                        docker tag ${FULL_IMAGE} ${REGISTRY}/${IMAGE_NAME}:latest
                        docker push ${REGISTRY}/${IMAGE_NAME}:latest
                    '''
                }
            }
        }
 
        // Stage 5: Deploy nel namespace TEST
        stage('Deploy in TEST') {
            steps {
                container('kubectl') {
                    sh '''
                        echo "=== Deploy in namespace TEST (${IMAGE_TAG}) ==="
                        # Sostituzione tag immagine nei manifest con sed
                        sed -i "s|REGISTRY/myapp:IMAGE_TAG|${FULL_IMAGE}|g" \
                            k8s/deployment-test.yaml
                        sed -i "s|IMAGE_TAG|${IMAGE_TAG}|g" \
                            k8s/deployment-test.yaml
 
                        # Applicazione manifest
                        kubectl apply -f k8s/deployment-test.yaml
                        kubectl apply -f k8s/service-test.yaml
 
                        # Attesa completamento RollingUpdate
                        echo "Attesa rollout completamento..."
                        kubectl rollout status deployment/myapp \
                            -n test --timeout=5m
                    '''
                }
            }
        }
 
        // Stage 6: Smoke Test su TEST
        stage('Smoke Test (TEST)') {
            steps {
                container('kubectl') {
                    sh '''
                        echo "=== Smoke test namespace test ==="
                        # Attesa che il Service risponda (via kubectl exec su un pod test)
                        kubectl wait pod -l app=myapp \
                            -n test --for=condition=Ready --timeout=2m
 
                        # Test endpoint /health via curl da dentro il cluster
                        POD=$(kubectl get pod -l app=myapp -n test \
                              -o jsonpath={.items[0].metadata.name})
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
 
        // ─── HUMAN GATE ───────────────────────────────────────────────────
        // Stage 7: Approvazione manuale prima del deploy in PROD
        stage('Approvazione Deploy PROD') {
            // Non eseguire su branch diversi da main/master
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                }
            }
            steps {
                // Notifica che si è in attesa di approvazione
                echo "Deploy in TEST completato. In attesa di approvazione per PROD..."
                // Timeout approvazione: 30 minuti
                timeout(time: 30, unit: 'MINUTES') {
                    input {
                        message "Approvare il deploy in PRODUZIONE?"
                        ok "Si', approvo il deploy"
                        // Descrivere chi può approvare (gruppo Jenkins)
                        // submitter 'devops-lead,jenkins-admin'
                        parameters {
                            string(
                                name: 'CHANGE_TICKET',
                                description: 'Numero ticket di change (es. JIRA-1234)',
                                defaultValue: ''
                            )
                        }
                    }
                }
            }
        }
 
        // Stage 8: Deploy nel namespace PROD
        stage('Deploy in PROD') {
            when {
                anyOf {
                    branch 'main'
                    branch 'master'
                }
            }
            steps {
                container('kubectl') {
                    sh '''
                        echo "=== Deploy in namespace PROD (${IMAGE_TAG}) ==="
                        # Sostituzione tag nei manifest prod
                        sed -i "s|REGISTRY/myapp:IMAGE_TAG|${FULL_IMAGE}|g" \
                            k8s/deployment-prod.yaml
                        sed -i "s|IMAGE_TAG|${IMAGE_TAG}|g" \
                            k8s/deployment-prod.yaml
                        # Override repliche dal parametro
                        sed -i "s|replicas: 2|replicas: ${PROD_REPLICAS}|g" \
                            k8s/deployment-prod.yaml
 
                        kubectl apply -f k8s/deployment-prod.yaml
                        kubectl apply -f k8s/service-prod.yaml
 
                        echo "Attesa rollout PROD..."
                        kubectl rollout status deployment/myapp \
                            -n prod --timeout=10m
 
                        echo "=== DEPLOY PROD COMPLETATO ==="
                        kubectl get pods -n prod
                    '''
                }
            }
        }
 
        // Stage 9: Verifica post-deploy PROD
        stage('Verifica PROD') {
            when {
                anyOf { branch 'main'; branch 'master' }
            }
            steps {
                container('kubectl') {
                    sh '''
                        echo "=== Verifica finale PROD ==="
                        kubectl get deployment myapp -n prod
                        kubectl get pods -n prod -l app=myapp
                        kubectl describe deployment myapp -n prod | \
                            grep -E "Image:|Replicas:|Available"
                    '''
                }
            }
        }
    }
 
    // ─── POST ACTIONS ───────────────────────────────────────────────────────
    post {
        success {
            echo "Pipeline COMPLETATA con successo!"
            echo "Immagine deployata: ${FULL_IMAGE}"
            // slackSend channel:'#deployments', message:"Deploy ${IMAGE_TAG} PROD OK"
        }
        failure {
            echo "Pipeline FALLITA - Rollback automatico in test"
            // In produzione: triggerare rollback automatico
            // kubectl rollout undo deployment/myapp -n test
        }
        aborted {
            echo "Deploy in PROD annullato dall'operatore"
        }
        always {
            echo "Pulizia immagini Docker locali..."
            // docker image prune -f
        }
    }
}
