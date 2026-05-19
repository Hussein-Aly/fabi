// ==========================================================================
// Copyright (c) Fabasoft R&D GmbH, A-4020 Linz, 1988-2026.
//
// Alle Rechte vorbehalten. Alle verwendeten Hard- und Softwarenamen sind
// Handelsnamen und/oder Marken der jeweiligen Hersteller.
//
// Der Nutzer des Computerprogramms anerkennt, dass der oben stehende
// Copyright-Vermerk im Sinn des Welturheberrechtsabkommens an der vom
// Urheber festgelegten Stelle in der Funktion des Computerprogramms
// angebracht bleibt, um den Vorbehalt des Urheberrechtes genuegend zum
// Ausdruck zu bringen. Dieser Urheberrechtsvermerk darf weder vom Kunden,
// Nutzer und/oder von Dritten entfernt, veraendert oder disloziert werden.
// ==========================================================================
//TODO Rename this file
def isBranchProtected
isBranchProtected = branch.isProtected()
def currentBranch = env.CHANGE_BRANCH ?: env.BRANCH_NAME
def targetBranch = env.CHANGE_TARGET ?: env.BRANCH_NAME


properties([
    buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '10', daysToKeepStr: '', numToKeepStr: '10')),
    parameters([
        booleanParam(
            name: 'checkout',
            defaultValue: (isBranchProtected || currentBranch.startsWith('renovate-') || targetBranch in ["master", "development","gateway-agent-refactor"]),
            description: "Checkout"
        ),
        booleanParam(
            name: 'test',
            defaultValue: (isBranchProtected || currentBranch.startsWith('renovate-') || targetBranch in ["master", "development","gateway-agent-refactor"]),
            description: "Unit Testing with Pytest"
        ),
        booleanParam(
            name: 'execute-loadtests',
            defaultValue: (isBranchProtected || env.BRANCH_NAME == "master"),
            description: "Load testing with lucust"
        ),
        booleanParam(
            name: 'linter-throw-error',
            defaultValue: (isBranchProtected || env.BRANCH_NAME == "master" || targetBranch == "master"),
            description: "Breaks the pipeline if linter fails"
        ),
        booleanParam(
            name: 'final-build-and-publish',
            defaultValue: (isBranchProtected || env.BRANCH_NAME == "master" || env.BRANCH_NAME == "development" || env.BRANCH_NAME == "gateway-agent-refactor" || targetBranch == "development"),
            description: "Do Final Build and Publish"
        ),
    ])
])

fabasoft.utils.globalWrapper {
    node(fabasoft.getNodeSelector(os: fabasoft.utils.OS_LINUX)) {
        def buildImage = "fabasoft/build-node:795" // renovate:docker
        if (params.checkout) {
            stage("checkout") {
                checkout scm
                fabasoft.utils.insideContainer(container: 'fabasoft/build-centos8:71') {
                    // renovate:docker
                    currentBuild.displayName = fabasoft.utils.getBuildVersion()

                }
            }
        }
        if (params.test) {
            stage("test") {
                stage("test-checkout") {
                    fabasoft.utils.checkoutGitlabRepo('cd/machines/common', 'master', true)
                }
                stage("test-build") {
                    sh 'chmod +x ./pre.sh'
                    sh './pre.sh'
                    testImage = docker.build("test-image", "--build-arg INSTALL_PYTEST=true --build-arg JWT_ENABLED=false .")
                }
                stage("test-pytests") {
                    testImage.inside {
                        sh '''
                        export COVERAGE_FILE=".coverage"
                        pytest tests/unit --maxfail=1 --disable-warnings --cov=mbai.aiserver --cov-report=term --cov-report=xml:coverage.xml
                        cat coverage.xml
                        '''
                        recordCoverage(tools: [[parser: 'COBERTURA', pattern: "coverage.xml"]], sourceDirectories: [[path: '/opt/app-root/']])
                    }
                }
                if (params['execute-loadtests']) {
                    stage("load-tests") {
                        testImage.inside("--env-file ${env.WORKSPACE}/.testenv_vars") {
                            // start server
                            sh "nohup uvicorn mbai.aiserver.api_server:app --host 0.0.0.0 --port 9000 --workers 1 > uvicorn.log 2>&1 &"
                            // Wait for the server to start
                            sh '''curl -sf --retry 20 --retry-delay 1 --retry-connrefused http://localhost:9000/'''
                            // lucust can also write a nice report with '--html report.html', but not sure how to publish to Jenkins UI
                            sh "locust -f tests/loadtests/locustfile.py --headless -u 100 -r 10 --host http://localhost:9000 --run-time 40s --only-summary"
                        }
                    }
                }
                stage("linter") {
                    testImage.inside {
                        sh "flake8 . --count --show-source --select=F ${params['linter-throw-error'] ? '' : '|| true'}"
                    }
                }
                stage("test-cleanup") {
                    sh 'docker rmi test-image'
                }
            }
        }
    }
    if (params['final-build-and-publish']) {
        stage("final-build-and-publish") {
            dockerBuildInfo = fabasoft.containerBuild(platform: 'linux', publishbuildinfo: true, dockerfilePaths: ['./Dockerfile'])
        }
   }
}


