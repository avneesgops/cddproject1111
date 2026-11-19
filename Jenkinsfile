pipeline {
    agent any

    triggers {
        // Refresh headlines every fifteen minutes; Jenkins spreads runs using H.
        cron('H/15 * * * *')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    parameters {
        choice(name: 'COUNTRY', choices: ['in', 'us', 'gb', 'ca', 'au'], description: 'Country for top headlines')
        choice(name: 'CATEGORY', choices: ['general', 'business', 'entertainment', 'health', 'science', 'sports', 'technology'], description: 'Headline category')
        booleanParam(name: 'USE_NEWSAPI_KEY', defaultValue: false, description: 'Use the optional newsapi-key Jenkins credential instead of the free RSS feed')
    }

    stages {
        stage('Check Python syntax') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'python3 -m compileall -q app.py verifynews scripts'
                    } else {
                        bat 'py -3 -m compileall -q app.py verifynews scripts'
                    }
                }
            }
        }

        stage('Refresh current headlines') {
            steps {
                script {
                    def country = params.COUNTRY.toLowerCase()
                    def category = params.CATEGORY
                    def refreshFeed = {
                        if (isUnix()) {
                            sh "python3 scripts/fetch_current_news.py --country ${country} --category ${category}"
                        } else {
                            bat "py -3 scripts\\fetch_current_news.py --country ${country} --category ${category}"
                        }
                    }
                    if (params.USE_NEWSAPI_KEY) {
                        withCredentials([string(credentialsId: 'newsapi-key', variable: 'NEWS_API_KEY')]) {
                            refreshFeed()
                        }
                    } else {
                        refreshFeed()
                    }
                }
            }
        }

        stage('Publish headline snapshot') {
            steps {
                archiveArtifacts artifacts: 'datasets/current_news.json', fingerprint: true
            }
        }
    }
}
