"""GraphQL documents for glints.com/api/v2/graphql.

These are written by hand against the introspected schema rather than copied
from the site bundle, so a webpack rebuild cannot rot them. They are plain
documents - Glints uses no persisted queries, no doc_id and no operation
allow-list, so nothing here is volatile.

One deliberate omission: the Job type exposes `creator { name lastSeen online }`,
which is the individual recruiter handling the posting. That is personal data
about a named person rather than information about the vacancy, so it is left
out of every selection. The hiring-responsiveness signals that sit alongside it
(isHighResponseRate, creatorResponseRate, creatorResponseTime) are properties of
the posting, and those are kept.
"""

# --- fragments ------------------------------------------------------------

F_COMPANY_CARD = """
fragment CompanyCard on Company {
  id name brandName logo status isVIP IndustryId
  industry { id name }
  verificationTier { type }
}
"""

F_COUNTRY = """
fragment CountryF on Country { code name }
"""

F_SALARY = """
fragment SalaryF on JobSalary {
  id salaryType salaryMode minAmount maxAmount CurrencyCode
}
"""

F_LOCATION = """
fragment LocationF on HierarchicalLocation {
  id name administrativeLevelName formattedName level slug latitude longitude
  parents {
    id name administrativeLevelName formattedName level slug
    CountryCode: countryCode
    parents { level formattedName slug }
  }
}
"""

F_CATEGORY = """
fragment CategoryF on HierarchicalJobCategory {
  id name level
  parents { id level name }
  children { id level name }
}
"""

# The v2 resolver is stricter than Apollo Server: a fragment that is defined but
# never spread fails validation outright ("Fragment X is never used"). So each
# operation below concatenates exactly the fragments it references, rather than
# sharing one blob.
JOB_FRAGMENTS = F_COMPANY_CARD + F_COUNTRY + F_SALARY + F_LOCATION + F_CATEGORY

# Shared shape for a job as it appears in a search result page.
JOB_CARD = """
  id title status type workArrangementOption educationLevel
  createdAt updatedAt isHot shouldShowSalary source jobSource fraudReportFlag
  minYearsOfExperience maxYearsOfExperience
  company { ...CompanyCard }
  city { id name }
  citySubDivision { id name }
  country { ...CountryF }
  salaries { ...SalaryF }
  location { ...LocationF }
  hierarchicalJobCategory { ...CategoryF }
  skills { skill { id name } mustHave }
"""

# --- operations -----------------------------------------------------------

SEARCH_JOBS = (
    """
query searchJobsV3($data: JobSearchConditionInput!) {
  searchJobsV3(data: $data) {
    hasMore
    expInfo
    jobsInPage { %s }
  }
}
""" % JOB_CARD
) + JOB_FRAGMENTS

# getJobById is the ungated route to a posting: it carries the description,
# benefits, interview process and address that never appear in a search card,
# and unlike search it has no page-2 login wall.
JOB_BY_ID = """
query getJobById($id: String) {
  getJobById(id: $id) {
    id title status type workArrangementOption educationLevel
    createdAt updatedAt expiryDate closedAt startDate endDate
    isRemote isHot isPublic isActivelyHiring isMatched
    shouldShowSalary shouldShowBenefits acceptsForeignApplications
    isCoverLetterMandatory screeningQuestionsEnabled resumeRequiredStatus
    isResumeRequiredForCandidate isEducationRequiredForCandidate
    isLocationRequiredForCandidate isProfilePicRequired
    minYearsOfExperience maxYearsOfExperience minAge maxAge gender
    source jobSource externalApplyURL fraudReportFlag labels
    isHighResponseRate creatorResponseRate creatorResponseTime
    descriptionJsonString interviewProcessJsonString
    salaries { ...SalaryF }
    salaryEstimate { minAmount maxAmount CurrencyCode }
    benefits { benefit title description logo }
    metadata { workingDaysPerWeek requiresWeekendHolidays workShifts }
    skills { skill { id name } mustHave }
    hierarchicalJobCategory { ...CategoryF }
    location { ...LocationF }
    city { id name }
    citySubDivision { id name }
    country { ...CountryF }
    companyAddress {
      id additionalAddressInfo
      poi { id name addressLabel placeId provider }
    }
    company {
      ...CompanyCard
      size website tagline address bannerPic
      isHiring localOffice descriptionJsonString
    }
  }
}
""" + JOB_FRAGMENTS

COMPANY_BY_ID = """
query getCompanyById($id: String, $data: GetCompanyByIdInput) {
  getCompanyById(id: $id, data: $data) {
    id name brandName displayName logo bannerPic status
    isVIP isHiring localOffice size website tagline address
    createdAt verifiedAt jobCount legalRegistrationNumber
    descriptionJsonString cultureJsonString
    photosJsonString socialMediaSitesJsonString
    industry { id name }
    verificationTier { type }
    hierarchicalLocation { ...LocationF }
    jobs { %s }
  }
}
""" % JOB_CARD + JOB_FRAGMENTS

SIMILAR_JOBS = (
    """
query getSimilarJobs($data: GetSimilarJobsInput) {
  getSimilarJobs(data: $data) {
    list { %s }
  }
}
""" % JOB_CARD
) + JOB_FRAGMENTS

# The facet counts behind the search page's filter rail: which companies,
# cities, categories and currencies actually carry jobs for a given query.
SEARCH_FILTERS = """
query getJobSearchFilters($filterCondition: JobSearchFiltersFilterInputV2!) {
  getJobSearchFiltersV2(data: $filterCondition) {
    jobTypes yearsOfExperienceRanges lastUpdatedAtRanges
    workArrangementOptions currencies educationLevels hasRemoteJobs
    companies { id name logo status isVIP }
    cities { id name country { name } }
    citySubDivisions { id name city { name } }
    jobRoles { id name level }
    hierarchicalLocations { ...LocationF }
  }
}
""" + F_LOCATION

JOB_TITLE_SUGGESTIONS = """
query getJobTitleSuggestions($keyword: String!, $countryCode: String, $limit: Int) {
  getJobTitleSuggestions(keyword: $keyword, countryCode: $countryCode, limit: $limit) {
    count
    jobTitles
    jobTitleSuggestions { title type }
  }
}
"""

SKILLS = """
query skills($input: QuerySkillsInput) {
  skills(input: $input) {
    count
    list { id name translationName relevanceScore }
  }
}
"""
