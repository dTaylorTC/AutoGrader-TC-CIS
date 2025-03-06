from __future__ import unicode_literals

import json
import logging
import os
import random
import string
import time
import zipfile
from datetime import datetime, timedelta
from os.path import basename
from shutil import copyfile

import mosspy
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver

from .grader import touch
from .storage import OverwriteStorage


def other_files_directory_path(instance, filename):
    return 'uploads/assignment/course_{0}/{1}/{2}'.format(instance.assignment.course.id, instance.assignment.title.replace(" ","-").lower(), filename)

def assignment_directory_path(instance, filename):
    return 'uploads/assignment/course_{0}/{1}/{2}'.format(instance.course.id, instance.title.replace(" ","-").lower(), filename)

def submission_directory_path(instance, filename):
    ts = time.time()
    st = datetime.fromtimestamp(ts).strftime('%Y-%m-%d-%H%M%S')
    return 'uploads/submission/student_{0}/assignment_{1}/{2}{3}'.format(instance.student.id, instance.assignment.id, st, filename)

def submission_key():
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))

def enroll_key():
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))

class Instructor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username

class Course(models.Model):
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, null=False, default=None)
    name = models.CharField(max_length=64)
    enroll_key = models.CharField(max_length=8, default=enroll_key, unique=True)
    course_id = models.CharField(max_length=64)
    max_extension_days = models.IntegerField(default=0)

    def __str__(self):
        return self.name

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_confirmed = models.BooleanField(default=False)
    submission_pass = models.CharField(max_length=12, default=submission_key)
    courses = models.ManyToManyField(Course)

    def get_roll_number(self):
        return self.user.email.split("@")[0]

    def student_username(self):
        return self.user.username
    student_username.short_description = 'Username'

    def student_firstname(self):
        return self.user.first_name
    student_firstname.short_description = 'First Name'

    def student_lastname(self):
        return self.user.last_name
    student_lastname.short_description = 'Last Name'

    def student_email(self):
        return self.user.email
    student_email.short_description = 'Email'

    def get_late_days_left(self, course):
        aes = AssignmentExtension.objects.filter(student=self, assignment__course=course)
        days_extended = aes.aggregate(Sum('days'))['days__sum']

        if days_extended is None:
            days_extended = 0
        late_days_left = course.max_extension_days - days_extended
        return late_days_left

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name + " (" + self.user.email + ")"

class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=False, default=None)
    title = models.CharField(max_length=64, null=False, default=None)
    description = models.TextField(max_length=8192, null=True, default=None)
    instructor_test = models.FileField(upload_to=assignment_directory_path, null=False, default=None, storage=OverwriteStorage())
    student_test = models.FileField(upload_to=assignment_directory_path, null=False, default=None, storage=OverwriteStorage())
    assignment_file = models.FileField(upload_to=assignment_directory_path, null=False, default=None, storage=OverwriteStorage())
    total_points = models.IntegerField(default=25)
    timeout = models.IntegerField(default=3)
    open_date = models.DateTimeField('open date', default=datetime.now)
    due_date = models.DateTimeField('due date', default=datetime.now)
    publish_date = models.DateTimeField('date published', default=datetime.now)

    class Meta:
        unique_together = ('course', 'title',)

    def corrected_due_date(self, student=None):
        aes = AssignmentExtension.objects.filter(assignment=self, student=student)
        days_extended = aes.aggregate(Sum('days'))['days__sum']

        if days_extended is None:
            days_extended = 0

        corrected_due_date = self.due_date + timedelta(days=days_extended)
        return corrected_due_date

    def get_student_and_latest_submissions(self):
        students = Student.objects.filter(courses=self.course).order_by('user__email')
        submissions = []
        for student in students:
            submission = Submission.objects.filter(student=student, assignment=self).order_by("-publish_date")
            student_submission_count = len(submission)
            submission = submission.first()
            submissions.append([submission, student, student_submission_count])

        return submissions

    def moss_report(self):
        moss_report = 'uploads/moss_submission/assignment_' + str(self.id) + "/" + str(self.id) + ".html"
        if os.path.exists(moss_report):
            return moss_report
        return False

    def moss_submit(self):
        moss_folder = 'uploads/moss_submission/assignment_{0}/'.format(self.id)
        submissions = self.get_student_and_latest_submissions()
        submission_count = 0
        for submission, student, _ in submissions:
            if submission is not None:
                modifiable_file = submission.get_modifiable_file()
                path = moss_folder + basename(modifiable_file).replace(".", "-" + submission.student.get_roll_number() + ".")
                touch(path)
                copyfile(modifiable_file, path)
                submission_count += 1

        if submission_count == 0:
            logging.debug("MOSS: No submissions available for generating Moss report")
            return False

        m = mosspy.Moss(settings.MOSS_USERID, "python")
        m.addBaseFile(self.assignment_file.url)
        m.addFilesByWildcard(moss_folder + "*.py")

        url = m.send()
        if url:
            logging.debug("MOSS: " + url)
            path = moss_folder + str(self.id) + ".html"
            touch(path)
            m.saveWebPage(url, path)
            return True
        else:
            logging.debug("MOSS: No url received.")
            return False

    def __str__(self):
        return self.title + " (" + self.course.course_id + ")"

class OtherFile(models.Model):
    file = models.FileField(upload_to=other_files_directory_path, null=False, default=None, storage=OverwriteStorage())
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)

class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    submission_file = models.FileField(upload_to=submission_directory_path, null=False)
    passed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    publish_date = models.DateTimeField('date published', default=datetime.now)

    def get_score(self):
        total = self.passed + self.failed
        if total == 0:
            return 0
        return float(self.passed) * self.assignment.total_points / total

    def get_modifiable_file(self):
        return self.submission_file.url.replace(".zip","")  + "/" + os.path.basename(self.assignment.assignment_file.url)

    def get_log_file(self):
        return self.submission_file.url.replace(".zip","")  + "/test-results.log"

    def assignment_course(self):
        return self.assignment.course
    assignment_course.short_description = 'Course'

    def __str__(self):
        return self.assignment.title + " (" + self.student.user.email + " - id: " + str(self.id) + ")"

class AssignmentExtension(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    days = models.IntegerField(default=0)

    def assignment_due_date(self):
        return self.assignment.due_date
    assignment_due_date.short_description = 'Due Date'

    def assignment_corrected_due_date(self):
        return self.assignment.corrected_due_date(self.student)
    assignment_corrected_due_date.short_description = 'Corrected Due Date'

    def course_max_extensions(self):
        return self.assignment.course.max_extension_days
    course_max_extensions.short_description = 'Total Extension Days for Course'

    def days_left_for_course(self):
        return self.student.get_late_days_left(self.assignment.course)
    days_left_for_course.short_description = 'Extension Days Left'

@receiver(post_save, sender=Assignment)
def create_assignment_zip_file(sender, instance, created, **kwargs):
    assignment_directory = assignment_directory_path(instance, "")
    zip_full_path = assignment_directory + "assignment" + str(instance.id) + ".zip"
    zip_file = zipfile.ZipFile(zip_full_path, 'w', zipfile.ZIP_DEFLATED)
    assignment_id = int(instance.id)
    student_config = {
        "assignment": int(assignment_id),
        "modifiable_files": [basename(instance.assignment_file.url)],
        "student_tests": [basename(instance.student_test.url)],
        "timeout": int(instance.timeout),
        "total_points": int(instance.total_points)
    }
    student_config_file = assignment_directory + "config.json"
    with open(student_config_file, 'w') as file:
        json.dump(student_config, file, indent=4)
    files = [instance.student_test.url, instance.assignment_file.url, student_config_file]
    other_files = OtherFile.objects.filter(assignment=instance)
    for other_file in other_files:
        files.append(other_file.file.url)
    with open("uploads/assignment/run.py","r") as file:
        content = file.read()
        content = content.replace("##RUN_API_URL##", settings.RUN_API_URL)
        zip_file.writestr("run.py", content)
    for file in files:
        zip_file.write(file, os.path.basename(file))
    zip_file.close()

@receiver(post_save, sender=OtherFile)
def create_assignment_zip_file_other_file(sender, instance, created, **kwargs):
    assignment_directory = assignment_directory_path(instance.assignment, "")
    zip_full_path = assignment_directory + "assignment" + str(instance.assignment.id) + ".zip"
    file = instance.file.url
    zip_file = zipfile.ZipFile(zip_full_path, 'a', zipfile.ZIP_DEFLATED)
    zip_file.write(file, os.path.basename(file))
    zip_file.close()