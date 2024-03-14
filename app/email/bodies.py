class EmailCode:
    code_for_registration = 'Your verification code for registration account: '

    code_for_delete = 'Your verification code for delete account: '

    code_for_change_username = ''

    code_for_change_email = 'Your verification code for change email address: '

    code_for_change_password = 'Your verification code for change password: '


class EmailInfo:
    registration_account_info = ("your account has been successfully registered. "
                                 "If it not you registered account, please, write a message to support.")

    delete_account_info = ("Your account has been successfully deleted. "
                           "If it not you deleted account, please, write a message to support.")

    change_username_info = ("Your username account has been successfully updated."
                            " If it not you updated username, please, write a message to support.")

    change_email_info = ("Your email address has been successfully updated."
                         " If it not you updated email address, please, write a message to support.")

    change_password_info = ("Your password has been successfully updated."
                            " If it not you updated password, please, write a message to support.")


class EmailInfoModerator:
    rename_user = ('The username of your account was changed by the moderator due to the fact that your previous'
                   ' username did not comply with the community rules. Write to support if you want to challenge'
                   ' the moderators decision.')

    delete_user = ('Your account was deleted by a moderator for violating community rules. Write to support if you'
                   ' want to challenge the moderators decision.')

    change_post = ('The moderator has changed one of your recent posts due to violations of the community rules.'
                   ' Write to support if you want to challenge the moderators decision.')

    delete_post = ('The moderator has deleted one of your recent posts due to violations of the community rules.'
                   ' Write to support if you want to challenge the moderators decision.')


class EmailInfoAdmin:
    delete_user = ('Your account was deleted by a admin for violating community rules. Write to support if you'
                   ' want to challenge the admins decision.')
